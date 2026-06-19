import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import redis
import stripe
from fastapi import HTTPException, status
from jose import jwt
from sqlmodel import Session, select
import httpx


from configs import settings
from models import (
    CheckoutSessionCreateData,
    Payment,
    PaymentIntentCreateData,
    PaymentStatus,
    PaymentWebhookEvent,
    RefundCreateData,
)

from seller_service import SellerService

logger = logging.getLogger("payments.payment_service")
stripe.api_key = settings.stripe_secret_key


def decode_user_id_from_token(access_token: Optional[str]) -> Optional[int]:
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.token_algorithm])
        user_id = payload.get("user_id")
        if isinstance(user_id, int):
            return user_id
        if isinstance(user_id, str) and user_id.isdigit():
            return int(user_id)
        return None
    except Exception:
        return None


def _to_metadata(payload: Dict[str, Any]) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        metadata[str(key)] = str(value)
    return metadata


def _publish_event(event_payload: Dict[str, Any]) -> None:
    try:
        redis_client = redis.Redis.from_url(settings.redis_url)
        redis_client.lpush(settings.payment_events_channel, json.dumps(event_payload))
    except Exception:
        logger.exception("Failed to publish payment event to Redis")


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def get_payment_by_id(self, payment_id: int) -> Payment:
        payment = self.db.get(Payment, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment

    def get_latest_payment_by_order_id(self, order_id: int) -> Payment:
        payment = self.db.exec(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.created_at.desc())
        ).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found for order")
        return payment
    
    def create_payment_intent(
        self,
        payload: PaymentIntentCreateData,
        *,
        request_id: Optional[str],
        buyer_id: Optional[int],
    ) -> Payment:
        if request_id:
            existing = self.db.exec(select(Payment).where(Payment.idempotency_key == request_id)).first()
            if existing:
                return existing

        if not settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe secret key is not configured",
            )

        stripe_metadata = _to_metadata(
            {
                "order_id": payload.order_id,
                "post_id": payload.post_id,
                "buyer_id": buyer_id,
                "seller_id": payload.seller_id,
                **(payload.metadata or {}),
            }
        )

        try:
            seller_service = SellerService(self.db)
            seller_stripe_id = seller_service.get_stripe_account_id(payload.seller_id)

            application_fee = int(payload.amount_cents * settings.application_fee)

            intent = stripe.PaymentIntent.create(
                amount=payload.amount_cents,
                currency=payload.currency.lower(),
                application_fee_amount=application_fee,  # 5% Ð¾ÑÑ‚Ð°Ñ‘Ñ‚ÑÑ Ñ‚ÐµÐ±Ðµ
                transfer_data={
                    "destination": seller_stripe_id,     # 95% â†’ Ð±Ð°Ð½Ðº Ð¿Ñ€Ð¾Ð´Ð°Ð²Ñ†Ð°
                },
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                metadata=stripe_metadata,
            )

            # create_payload: Dict[str, Any] = {
            #     "amount": payload.amount_cents,
            #     "currency": payload.currency.lower(),
            #     "description": payload.description,
            #     "automatic_payment_methods": {
            #         "enabled": True,
            #         "allow_redirects": "never",
            #     },
            #     "metadata": stripe_metadata,
            #     "idempotency_key": request_id or None,
            # }

            # if payload.confirm:
            #     create_payload["confirm"] = True
            #     if payload.test_payment_method:
            #         create_payload["payment_method"] = payload.test_payment_method

            # intent = stripe.PaymentIntent.create(
            #     **create_payload,
            # )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

        payment = Payment(
            order_id=payload.order_id,
            post_id=payload.post_id,
            buyer_id=buyer_id,
            seller_id=payload.seller_id,
            amount_cents=payload.amount_cents,
            currency=payload.currency.lower(),
            description=payload.description,
            status=intent.status,
            provider_payment_intent_id=intent.id,
            client_secret=intent.client_secret,
            payment_metadata=payload.metadata or {},
            idempotency_key=request_id,
            request_id=request_id,
            updated_at=datetime.utcnow(),
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def create_checkout_session(
        self,
        payload: CheckoutSessionCreateData,
        *,
        request_id: Optional[str],
        buyer_id: Optional[int],
    ) -> Dict[str, Any]:
        if request_id:
            existing = self.db.exec(select(Payment).where(Payment.idempotency_key == request_id)).first()
            if existing and existing.provider_checkout_session_id:
                return {
                    "payment": existing,
                    "checkout_session_id": existing.provider_checkout_session_id,
                    "checkout_url": (existing.payment_metadata or {}).get("checkout_url", ""),
                }

        stripe_metadata = _to_metadata(
            {
                "order_id": payload.order_id,
                "post_id": payload.post_id,
                "buyer_id": buyer_id,
                "seller_id": payload.seller_id,
                **(payload.metadata or {}),
            }
        )

        # Auto-create Stripe Express account for seller if not exists.
        # payouts_enabled is NOT required here — money goes to platform escrow.
        # The seller completes onboarding later; payouts_enabled is enforced at release_payment_to_seller.
        if payload.seller_id:
            seller_service = SellerService(self.db)
            try:
                seller_service.get_or_create_stripe_account(payload.seller_id)
            except Exception:
                logger.warning(
                    "Could not auto-create Stripe account for seller | seller_id=%s",
                    payload.seller_id,
                )

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                success_url=payload.success_url,
                cancel_url=payload.cancel_url,
                customer_email=payload.buyer_email,
                line_items=[
                    {
                        "price_data": {
                            "currency": payload.currency.lower(),
                            "product_data": {
                                "name": payload.product_name,
                                "description": payload.description,
                            },
                            "unit_amount": payload.amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                metadata=stripe_metadata,
                payment_intent_data={
                    "metadata": stripe_metadata,
                },
            )
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe checkout error: {str(exc)}")

        payment = Payment(
            order_id=payload.order_id,
            post_id=payload.post_id,
            buyer_id=buyer_id,
            seller_id=payload.seller_id,
            amount_cents=payload.amount_cents,
            currency=payload.currency.lower(),
            description=payload.description,
            status=PaymentStatus.REQUIRES_PAYMENT_METHOD.value,
            provider_checkout_session_id=session.id,
            delivery_cost_cents=payload.delivery_cost_cents,
            payment_metadata={
                **(payload.metadata or {}),
                "checkout_url": session.url,
            },
            idempotency_key=request_id,
            request_id=request_id,
            updated_at=datetime.utcnow(),
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        return {
            "payment": payment,
            "checkout_session_id": session.id,
            "checkout_url": session.url,
        }

    def get_checkout_session_status(self, session_id: str) -> Dict[str, Any]:
        try:
            session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe checkout status error: {str(exc)}")

        payment = self.db.exec(
            select(Payment).where(Payment.provider_checkout_session_id == session_id)
        ).first()

        is_paid = (session.get("payment_status") == "paid")
        status_value = PaymentStatus.SUCCEEDED.value if is_paid else PaymentStatus.REQUIRES_PAYMENT_METHOD.value
        payment_intent = session.get("payment_intent")
        payment_intent_id = None
        if isinstance(payment_intent, dict):
            payment_intent_id = payment_intent.get("id")
        elif isinstance(payment_intent, str):
            payment_intent_id = payment_intent

        if payment:
            payment.updated_at = datetime.utcnow()
            payment.status = status_value
            if payment_intent_id:
                payment.provider_payment_intent_id = payment_intent_id
            if is_paid and not payment.paid_at:
                payment.paid_at = datetime.utcnow()
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)

        return {
            "payment": payment,
            "checkout_session_id": session_id,
            "payment_status": session.get("payment_status", "unknown"),
            "status": status_value,
            "paid": is_paid,
            "order_id": payment.order_id if payment else None,
            "provider_payment_intent_id": payment_intent_id,
        }

    def refund_payment(self, payment_id: int, payload: RefundCreateData) -> Payment:
        payment = self.get_payment_by_id(payment_id)

        if not payment.provider_payment_intent_id:
            raise HTTPException(status_code=400, detail="Payment has no Stripe payment_intent id")

        refund_args: Dict[str, Any] = {
            "payment_intent": payment.provider_payment_intent_id,
        }
        if payload.amount_cents:
            refund_args["amount"] = payload.amount_cents
        if payload.reason:
            refund_args["reason"] = payload.reason
        if payload.metadata:
            refund_args["metadata"] = _to_metadata(payload.metadata)

        try:
            refund = stripe.Refund.create(**refund_args)
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe refund error: {str(exc)}")

        if payload.amount_cents and payload.amount_cents < payment.amount_cents:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED.value
        else:
            payment.status = PaymentStatus.REFUNDED.value
            payment.refunded_at = datetime.utcnow()

        payment.updated_at = datetime.utcnow()
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        _publish_event(
            {
                "event": "payment_refunded",
                "payment_id": payment.id,
                "provider": "stripe",
                "stripe_refund_id": refund.get("id"),
                "status": payment.status,
                "order_id": payment.order_id,
            }
        )

        return payment

    def process_stripe_webhook(self, *, payload: bytes, signature: str) -> Dict[str, Any]:
        if not settings.stripe_webhook_secret:
            raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

        try:
            event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

        event_id = event.get("id")
        event_type = event.get("type")
        if not event_id or not event_type:
            raise HTTPException(status_code=400, detail="Malformed Stripe event")

        already_processed = self.db.exec(
            select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider_event_id == event_id)
        ).first()
        if already_processed:
            return {"processed": True, "duplicate": True, "event_id": event_id, "event_type": event_type}

        event_object = event.get("data", {}).get("object", {})
        payment_intent_id = event_object.get("id")
        if event_type == "charge.refunded":
            payment_intent_id = event_object.get("payment_intent")

        payment = None
        if payment_intent_id:
            payment = self.db.exec(
                select(Payment).where(Payment.provider_payment_intent_id == payment_intent_id)
            ).first()

        if payment:
            payment.updated_at = datetime.utcnow()

            if event_type == "payment_intent.succeeded":
                payment.status = PaymentStatus.SUCCEEDED.value
                payment.paid_at = datetime.utcnow()
                latest_charge = event_object.get("latest_charge")
                if latest_charge:
                    payment.provider_charge_id = str(latest_charge)

                self._notify_delivery_service_on_payment_success(payment)

            elif event_type == "payment_intent.payment_failed":
                payment.status = PaymentStatus.FAILED.value
                error_info = event_object.get("last_payment_error", {})
                payment.last_error = error_info.get("message")

            elif event_type == "payment_intent.canceled":
                payment.status = PaymentStatus.CANCELED.value

            elif event_type == "charge.refunded":
                amount_refunded = int(event_object.get("amount_refunded") or 0)
                amount_total = int(event_object.get("amount") or 0)
                if amount_refunded >= amount_total and amount_total > 0:
                    payment.status = PaymentStatus.REFUNDED.value
                    payment.refunded_at = datetime.utcnow()
                else:
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED.value

            self.db.add(payment)

        webhook_event = PaymentWebhookEvent(
            provider_event_id=event_id,
            event_type=event_type,
            payload=event,
            processed_at=datetime.utcnow(),
        )
        self.db.add(webhook_event)
        self.db.commit()

        _publish_event(
            {
                "event": "stripe_webhook_processed",
                "event_type": event_type,
                "event_id": event_id,
                "payment_id": payment.id if payment else None,
            }
        )

        return {
            "processed": True,
            "duplicate": False,
            "event_id": event_id,
            "event_type": event_type,
            "payment_id": payment.id if payment else None,
        }
    
    def release_payment_to_seller(self, payment_id: int) -> Payment:
        """Transfer held payment funds to the seller after buyer confirmation."""
        payment = self.get_payment_by_id(payment_id)

        if payment.seller_transfer_id:
            return payment  # idempotent

        if payment.status not in (
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.TRANSFERRED.value,
            PaymentStatus.PENDING_TRANSFER.value,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot release payment in status '{payment.status}'"
            )

        if not payment.seller_id:
            raise HTTPException(status_code=400, detail="Payment has no seller_id")

        seller_service = SellerService(self.db)
        account = seller_service.get_or_create_stripe_account(payment.seller_id)

        if not account.payouts_enabled:
            payment.status = PaymentStatus.PENDING_TRANSFER.value
            payment.updated_at = datetime.utcnow()
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
            logger.warning(
                "Payment queued for transfer -- seller onboarding incomplete | "
                "payment_id=%s | seller_id=%s",
                payment.id, payment.seller_id,
            )
            return payment

        seller_stripe_id = account.stripe_account_id

        delivery_cost_cents = payment.delivery_cost_cents or 0
        product_cost_cents = payment.amount_cents - delivery_cost_cents
        seller_amount = int(product_cost_cents / (1 + settings.application_fee))


        # Resolve charge_id for source_transaction so the transfer draws from
        # the specific charge funds (pending OK) instead of available balance.
        charge_id = payment.provider_charge_id
        if not charge_id and payment.provider_payment_intent_id:
            try:
                pi = stripe.PaymentIntent.retrieve(payment.provider_payment_intent_id)
                charge_id = pi.get("latest_charge")
                if charge_id:
                    payment.provider_charge_id = charge_id
                    self.db.add(payment)
                    self.db.commit()
            except Exception:
                logger.warning(
                    "Could not retrieve charge_id from PaymentIntent | payment_id=%s",
                    payment.id,
                )

        transfer_args: Dict[str, Any] = {
            "amount": seller_amount,
            "currency": payment.currency.lower(),
            "destination": seller_stripe_id,
            "transfer_group": f"order_{payment.order_id}",
            "metadata": {"payment_id": str(payment.id), "order_id": str(payment.order_id)},
        }
        if charge_id:
            transfer_args["source_transaction"] = charge_id

        try:
            transfer = stripe.Transfer.create(**transfer_args)
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe transfer error: {str(exc)}")

        payment.seller_transfer_id = transfer.id
        payment.status = PaymentStatus.TRANSFERRED.value
        payment.transferred_at = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        _publish_event({
            "event": "payment_transferred_to_seller",
            "payment_id": payment.id,
            "order_id": payment.order_id,
            "transfer_id": transfer.id,
            "seller_amount_cents": seller_amount,
        })

        logger.info(
            "Payment released to seller | payment_id=%s | order_id=%s | "
            "transfer_id=%s | amount_cents=%s",
            payment.id, payment.order_id, transfer.id, seller_amount,
        )
        return payment
    def retry_pending_transfers_for_seller(self, seller_id: int) -> int:
        """Retry PENDING_TRANSFER payments for a seller that just completed onboarding."""
        pending = self.db.exec(
            select(Payment).where(
                Payment.seller_id == seller_id,
                Payment.status == PaymentStatus.PENDING_TRANSFER.value,
                Payment.seller_transfer_id == None,
            )
        ).all()

        released = 0
        for payment in pending:
            try:
                self.release_payment_to_seller(payment.id)
                released += 1
            except Exception:
                logger.exception(
                    "Retry transfer failed | payment_id=%s | seller_id=%s",
                    payment.id, seller_id,
                )
        return released

    def _notify_delivery_service_on_payment_success(self, payment: Payment) -> None:
        """Ð£Ð²ÐµÐ´Ð¾Ð¼Ð¸Ñ‚ÑŒ delivery-service Ð¾ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾Ð¹ Ð¾Ð¿Ð»Ð°Ñ‚Ðµ"""
        if not payment.order_id:
            return
        
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{settings.delivery_service_url}/api/v1/delivery/orders/{payment.order_id}/after-payment",
                    json={"order_id": payment.order_id, "payment_id": payment.id}
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"Delivery service notified | order_id={payment.order_id}")
        
        except Exception as e:
            logger.error(f"Failed to notify delivery service: {e}")



