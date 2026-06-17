import pytest
from unittest.mock import patch, MagicMock

from worker.billing_tasks import sync_stripe_customers, process_invoice_payment

@pytest.mark.anyio
@patch("worker.billing_tasks.stripe")
async def test_sync_stripe_customers(mock_stripe):
    mock_stripe.Customer.list.return_value = {"data": [{"id": "cus_123", "email": "test@example.com"}]}
    
    # Just checking basic execution path for coverage
    with patch("worker.billing_tasks.Session") as mock_session:
        session_instance = mock_session.return_value.__enter__.return_value
        session_instance.exec.return_value.first.return_value = None
        
        result = sync_stripe_customers()
        assert result is True
        mock_stripe.Customer.list.assert_called_once()

@pytest.mark.anyio
@patch("worker.billing_tasks.stripe")
async def test_process_invoice_payment(mock_stripe):
    mock_stripe.Invoice.retrieve.return_value = {"id": "in_123", "status": "paid", "customer": "cus_123"}
    
    with patch("worker.billing_tasks.Session") as mock_session:
        session_instance = mock_session.return_value.__enter__.return_value
        mock_user = MagicMock()
        mock_user.id = "user_1"
        session_instance.exec.return_value.first.return_value = mock_user
        
        result = process_invoice_payment("in_123")
        assert result is True
        mock_stripe.Invoice.retrieve.assert_called_once_with("in_123")
