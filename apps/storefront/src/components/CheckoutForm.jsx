import React, { useState } from 'react';
import { useStripe, useElements, CardElement } from '@stripe/react-stripe-js';
import { CreditCard, Loader2 } from 'lucide-react';
import axios from 'axios';

const apiClient = axios.create({ baseURL: 'http://localhost/api' });

export default function CheckoutForm({ cart, onPaymentSuccess }) {
    const stripe = useStripe();
    const elements = useElements();
    const [error, setError] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!stripe || !elements || cart.length === 0) return;

        setIsProcessing(true);
        setError(null);

        try {
            // 1. Create Payment Intent on Monolith
            const totalAmount = cart.reduce((sum, item) => sum + item.price, 0);
            const res = await apiClient.post('/v1/create-payment-intent/', {
                amount: totalAmount,
                product_id: cart[0].id,
                user_id: Math.floor(Math.random() * 1000)
            });

            const clientSecret = res.data.client_secret;

            // 2. Confirm Payment with Stripe
            const payload = await stripe.confirmCardPayment(clientSecret, {
                payment_method: {
                    card: elements.getElement(CardElement),
                }
            });

            if (payload.error) {
                setError(payload.error.message);
            } else {
                // Success! Webhook will handle the rest in the backend
                onPaymentSuccess();
            }
        } catch (err) {
            setError("Payment failed. Make sure you added Stripe keys to .env and restarted docker.");
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-md">
                <CardElement options={{
                    style: {
                        base: {
                            fontSize: '16px',
                            color: '#424770',
                            '::placeholder': { color: '#aab7c4' },
                        },
                        invalid: { color: '#9e2146' },
                    },
                }} />
            </div>

            {error && <div className="text-red-500 text-sm font-medium">{error}</div>}

            <button
                type="submit"
                disabled={!stripe || isProcessing}
                className="w-full flex justify-center items-center py-3 bg-yellow-400 hover:bg-yellow-500 text-gray-900 rounded-lg font-bold transition-colors shadow-sm disabled:opacity-50"
            >
                {isProcessing ? <Loader2 className="animate-spin mr-2" /> : <CreditCard className="mr-2 h-5 w-5" />}
                {isProcessing ? 'Processing...' : `Place your order`}
            </button>
            <p className="text-xs text-gray-500 text-center">
                Use 4242 4242 4242 4242 for testing
            </p>
        </form>
    );
}
