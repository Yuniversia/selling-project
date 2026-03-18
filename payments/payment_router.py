from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from sqlmodel import Session

from api_response import success_response
from database import get_session
from models import (
    CheckoutSessionCreateData,
    CheckoutSessionResponse,
    CheckoutSessionStatusResponse,
    PaymentIntentCreateData,
    PaymentIntentResponse,
    RefundCreateData,
)
from payment_service import PaymentService, decode_user_id_from_token


payments_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payments_router.post("/intents", status_code=status.HTTP_202_ACCEPTED)
def create_payment_intent(
    request: Request,
    payload: PaymentIntentCreateData,
    access_token: str = Cookie(None),
    x_request_id: str = Header(default=None, alias="X-Request-ID"),
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    buyer_id = decode_user_id_from_token(access_token)

    payment = service.create_payment_intent(
        payload,
        request_id=x_request_id,
        buyer_id=buyer_id,
    )

    response_payload = PaymentIntentResponse.model_validate(payment).model_dump(mode="json")
    return success_response(
        request,
        response_payload,
        meta={"idempotency_key": x_request_id, "provider": "stripe"},
    )


@payments_router.post("/checkout-sessions", status_code=status.HTTP_202_ACCEPTED)
def create_checkout_session(
    request: Request,
    payload: CheckoutSessionCreateData,
    access_token: str = Cookie(None),
    x_request_id: str = Header(default=None, alias="X-Request-ID"),
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    buyer_id = decode_user_id_from_token(access_token)

    created = service.create_checkout_session(
        payload,
        request_id=x_request_id,
        buyer_id=buyer_id,
    )
    payment = created["payment"]

    response_payload = CheckoutSessionResponse(
        payment_id=payment.id,
        checkout_session_id=created["checkout_session_id"],
        checkout_url=created["checkout_url"],
        order_id=payment.order_id,
        status=payment.status,
    ).model_dump(mode="json")

    return success_response(
        request,
        response_payload,
        meta={"idempotency_key": x_request_id, "provider": "stripe"},
    )


@payments_router.get("/checkout-sessions/{session_id}")
def get_checkout_session_status(
    request: Request,
    session_id: str,
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    result = service.get_checkout_session_status(session_id)
    response_payload = CheckoutSessionStatusResponse(
        payment_id=result["payment"].id if result["payment"] else None,
        checkout_session_id=result["checkout_session_id"],
        payment_status=result["payment_status"],
        status=result["status"],
        paid=result["paid"],
        order_id=result["order_id"],
        provider_payment_intent_id=result["provider_payment_intent_id"],
    ).model_dump(mode="json")
    return success_response(request, response_payload)


@payments_router.get("/{payment_id}")
def get_payment(
    request: Request,
    payment_id: int,
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    payment = service.get_payment_by_id(payment_id)
    response_payload = PaymentIntentResponse.model_validate(payment).model_dump(mode="json")
    return success_response(request, response_payload)


@payments_router.post("/{payment_id}/refund", status_code=status.HTTP_202_ACCEPTED)
def create_refund(
    request: Request,
    payment_id: int,
    payload: RefundCreateData,
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    payment = service.refund_payment(payment_id=payment_id, payload=payload)
    response_payload = PaymentIntentResponse.model_validate(payment).model_dump(mode="json")
    return success_response(request, response_payload)


@payments_router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_session),
):
    service = PaymentService(db)
    payload = await request.body()
    result = service.process_stripe_webhook(payload=payload, signature=stripe_signature)
    return Response(content="ok", media_type="text/plain", status_code=200) if result else Response(status_code=204)
