import os
import secrets
from datetime import datetime, timezone
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    customer_reference: str = Field(min_length=1, max_length=100)
    amount_minor: int = Field(strict=True, gt=0, le=1_000_000)
    currency: Literal["USD"] = "USD"


class OrderResponse(BaseModel):
    id: UUID
    customer_reference: str
    amount_minor: int
    currency: Literal["USD"]
    status: Literal["PENDING"]
    created_at: datetime


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(api_key: str | None = None) -> FastAPI:
    expected_key = api_key if api_key is not None else os.environ.get("ORDERFLOW_API_KEY")
    if not expected_key or len(expected_key) < 32:
        raise RuntimeError("Set ORDERFLOW_API_KEY to a secret of at least 32 characters.")

    app = FastAPI(
        title="OrderFlow API",
        version="0.1.0",
        description="Simulated orders. Day 1: single-process in-memory storage, local development only.",
    )
    orders: dict[UUID, OrderResponse] = {}
    records: dict[str, tuple[OrderCreate, UUID]] = {}
    store_lock = Lock()

    def require_api_key(supplied: Annotated[str | None, Depends(api_key_header)]) -> None:
        if supplied is None or not secrets.compare_digest(supplied.encode(), expected_key.encode()):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/health/live", tags=["Health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    def ready() -> dict[str, str]:
        return {"status": "ready", "storage": "in-memory"}

    @app.post("/api/v1/orders", response_model=OrderResponse, status_code=201,
              dependencies=[Depends(require_api_key)], tags=["Orders"])
    def create_order(
        payload: OrderCreate,
        response: Response,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    ) -> OrderResponse:
        if not idempotency_key.strip():
            raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank")
        with store_lock:
            previous = records.get(idempotency_key)
            if previous is not None:
                old_payload, order_id = previous
                if old_payload != payload:
                    raise HTTPException(status_code=409, detail="Idempotency key already used with a different payload")
                response.status_code = 200
                response.headers["Idempotency-Replayed"] = "true"
                return orders[order_id]
            order = OrderResponse(
                id=uuid4(), customer_reference=payload.customer_reference,
                amount_minor=payload.amount_minor, currency=payload.currency,
                status="PENDING", created_at=datetime.now(timezone.utc),
            )
            orders[order.id] = order
            records[idempotency_key] = (payload.model_copy(deep=True), order.id)
            response.headers["Location"] = f"/api/v1/orders/{order.id}"
            response.headers["Idempotency-Replayed"] = "false"
            return order

    @app.get("/api/v1/orders/{order_id}", response_model=OrderResponse,
             dependencies=[Depends(require_api_key)], tags=["Orders"])
    def get_order(order_id: UUID) -> OrderResponse:
        with store_lock:
            order = orders.get(order_id)
            if order is None:
                raise HTTPException(status_code=404, detail="Order not found")
            return order

    return app
