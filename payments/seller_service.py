import stripe
from fastapi import HTTPException
from sqlmodel import Session, select
from models import SellerPayoutAccount, SellerOnboardingStatus
from datetime import datetime


class SellerService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_stripe_account(self, seller_id: int) -> SellerPayoutAccount:
        existing = self.db.exec(
            select(SellerPayoutAccount).where(SellerPayoutAccount.seller_id == seller_id)
        ).first()
        if existing:
            return existing

        # Creating Express account for seller
        account = stripe.Account.create(
            type="express",
            capabilities={
                "transfers": {"requested": True},
            },
            settings={
                "payouts": {
                    "schedule": {"interval": "manual"},  # you control when
                }
            },
        )

        record = SellerPayoutAccount(
            seller_id=seller_id,
            stripe_account_id=account.id,
            onboarding_status=SellerOnboardingStatus.PENDING.value,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def create_onboarding_link(
        self, seller_id: int, return_url: str, refresh_url: str
    ) -> str:
        account = self.get_or_create_stripe_account(seller_id)

        link = stripe.AccountLink.create(
            account=account.stripe_account_id,
            type="account_onboarding",
            return_url=return_url,   # When seller finishes onboarding, they will be redirected here
            refresh_url=refresh_url, # if the link expires
        )
        return link.url

    def sync_account_status(self, seller_id: int) -> SellerPayoutAccount:
        """Call this after return_url or via the account.updated webhook"""
        record = self.db.exec(
            select(SellerPayoutAccount).where(SellerPayoutAccount.seller_id == seller_id)
        ).first()
        if not record:
            raise HTTPException(404, "Seller payout account not found")

        account = stripe.Account.retrieve(record.stripe_account_id)
        record.payouts_enabled = account.payouts_enabled
        record.details_submitted = account.details_submitted
        record.onboarding_status = (
            SellerOnboardingStatus.COMPLETED.value
            if account.payouts_enabled
            else SellerOnboardingStatus.PENDING.value
        )
        record.updated_at = datetime.utcnow()
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_onboarding_status(self, seller_id: int) -> dict:
        """Return seller onboarding status without creating a Stripe account."""
        record = self.db.exec(
            select(SellerPayoutAccount).where(SellerPayoutAccount.seller_id == seller_id)
        ).first()
        if not record:
            return {"payouts_enabled": False, "onboarding_status": "not_started", "needs_onboarding": True}
        return {
            "payouts_enabled": record.payouts_enabled,
            "onboarding_status": record.onboarding_status,
            "needs_onboarding": not record.payouts_enabled,
        }

    def get_stripe_account_id(self, seller_id: int) -> str:
        """Used in PaymentService when creating a payment"""
        record = self.db.exec(
            select(SellerPayoutAccount).where(SellerPayoutAccount.seller_id == seller_id)
        ).first()
        if not record or not record.payouts_enabled:
            raise HTTPException(
                400,
                "Seller has not completed payout setup. "
                "Direct them to complete onboarding first."
            )
        return record.stripe_account_id