import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShoppingCart, Package, CheckCircle2, AlertCircle, Clock, Search, Menu, Play } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import CheckoutForm from './components/CheckoutForm';

// Stripe Promise (Uses Vite Env Var, fallback to placeholder)
const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || "pk_test_placeholder");

const apiClient = axios.create({ baseURL: 'http://localhost/api' });

const products = [
  { id: 'prod-echo', name: 'Echo Dot (5th Gen) | Smart speaker with Alexa', price: 49.99, image: '🔵', rating: '★★★★☆', prime: true },
  { id: 'prod-kindle', name: 'Kindle Paperwhite (8 GB) - Now with a 6.8" display', price: 139.99, image: '📱', rating: '★★★★★', prime: true },
  { id: 'prod-coffee', name: 'Keurig K-Classic Coffee Maker', price: 89.99, image: '☕', rating: '★★★★☆', prime: false },
  { id: 'prod-buds', name: 'Wireless Earbuds with Active Noise Cancelling', price: 199.99, image: '🎧', rating: '★★★☆☆', prime: true },
];

export default function App() {
  const [cart, setCart] = useState([]);
  const [orders, setOrders] = useState([]);
  const [paymentSuccess, setPaymentSuccess] = useState(false);

  // Poll Orders from V2 Microservice
  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const res = await apiClient.get('/v2/orders/');
        setOrders(res.data);
      } catch (err) { }
    };
    fetchOrders();
    const interval = setInterval(fetchOrders, 2000);
    return () => clearInterval(interval);
  }, []);

  const addToCart = (product) => {
    setCart((prev) => [...prev, product]);
    setPaymentSuccess(false); // reset state if they buy again
  };

  const currentTotal = cart.reduce((s, i) => s + i.price, 0).toFixed(2);

  return (
    <div className="min-h-screen font-sans bg-gray-100">
      {/* Amazon Header */}
      <header className="bg-[#131921] text-white">
        <div className="flex items-center p-2 gap-4">
          <div className="flex items-center ml-2 cursor-pointer border border-transparent hover:border-white p-1 rounded">
            <h1 className="text-2xl font-bold tracking-tighter">amazon</h1>
            <span className="text-xs text-gray-300 ml-1 mt-2">.demo</span>
          </div>

          <div className="flex-grow flex items-center bg-white rounded-md overflow-hidden h-10 border-2 border-transparent focus-within:border-yellow-400 focus-within:ring-0">
            <select className="bg-gray-100 text-gray-700 h-full px-2 border-r border-gray-300 text-sm outline-none cursor-pointer hidden md:block">
              <option>All</option>
            </select>
            <input type="text" className="h-full w-full px-4 text-black outline-none" placeholder="Search Amazon-Demo" />
            <button className="bg-[#febd69] hover:bg-[#f3a847] h-full px-4 transition-colors">
              <Search className="h-5 w-5 text-gray-900" />
            </button>
          </div>

          <div className="hidden md:block border border-transparent hover:border-white p-1 rounded cursor-pointer">
            <div className="text-xs">Hello, sign in</div>
            <div className="text-sm font-bold">Account & Lists</div>
          </div>

          <div className="hidden md:block border border-transparent hover:border-white p-1 rounded cursor-pointer">
            <div className="text-xs">Returns</div>
            <div className="text-sm font-bold">& Orders</div>
          </div>

          <div className="flex items-center gap-1 border border-transparent hover:border-white p-1 rounded cursor-pointer relative pr-2">
            <ShoppingCart className="h-8 w-8" />
            <span className="absolute top-0 left-4 text-[#f08804] font-bold">{cart.length}</span>
            <span className="mt-3 font-bold">Cart</span>
          </div>
        </div>

        {/* Amazon Sub-nav */}
        <div className="bg-[#232f3e] p-2 flex items-center gap-4 text-sm px-4">
          <div className="flex items-center gap-1 font-bold cursor-pointer border border-transparent hover:border-white p-1 rounded">
            <Menu className="w-5 h-5" /> All
          </div>
          <span className="cursor-pointer border border-transparent hover:border-white p-1 rounded">Today's Deals</span>
          <span className="cursor-pointer border border-transparent hover:border-white p-1 rounded">Customer Service</span>
          <span className="cursor-pointer border border-transparent hover:border-white p-1 rounded">Registry</span>
          <span className="cursor-pointer border border-transparent hover:border-white p-1 rounded">Gift Cards</span>
          <span className="cursor-pointer border border-transparent hover:border-white p-1 rounded">Sell</span>
        </div>
      </header>

      <main className="max-w-[1500px] mx-auto pb-8">
        {/* Hero Carousel Banner Placeholder */}
        <div className="w-full h-[300px] bg-gradient-to-b from-slate-800 to-gray-100 flex items-center justify-center relative -z-10"
          style={{ maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)", WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)" }}>
          {/* In a real site, this is a hero image */}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 px-4 -mt-36" style={{ zIndex: 10 }}>

          {/* Main Product Catalog */}
          <div className="xl:col-span-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {products.map((p) => (
                <div key={p.id} className="bg-white p-5 rounded z-10">
                  <h3 className="text-lg font-bold text-gray-900 mb-2 truncate" title={p.name}>{p.name}</h3>
                  <div className="h-40 bg-gray-50 flex items-center justify-center text-8xl mb-4">
                    {p.image}
                  </div>
                  <div className="text-yellow-500 text-sm mb-1">{p.rating}</div>
                  <div className="flex items-start">
                    <span className="text-sm font-medium leading-none mt-1">$</span>
                    <span className="text-2xl font-bold leading-none">{Math.floor(p.price)}</span>
                    <span className="text-sm font-medium leading-none mt-1">{(p.price % 1).toFixed(2).substring(1)}</span>
                  </div>
                  {p.prime && <div className="text-blue-500 font-bold italic text-sm my-1">prime</div>}
                  <button
                    onClick={() => addToCart(p)}
                    className="mt-4 w-full py-1.5 bg-yellow-400 hover:bg-yellow-500 text-sm rounded-full font-medium shadow-sm border border-yellow-500"
                  >
                    Add to Cart
                  </button>
                </div>
              ))}

              {/* Video Content Block */}
              <div className="bg-white p-5 rounded z-10 col-span-1 sm:col-span-2 lg:col-span-4 mt-2">
                <h2 className="text-xl font-bold mb-4">Prime Video: Watch Now</h2>
                <div className="h-[200px] bg-slate-900 rounded-lg flex items-center justify-center cursor-pointer hover:bg-slate-800 transition">
                  <div className="flex items-center gap-2 text-white">
                    <Play className="w-12 h-12 text-blue-400" />
                    <span className="text-xl font-bold">Start your 30-day free trial</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Sidebar */}
          <div className="space-y-6">

            {/* Cart & Stripe Form */}
            <div className="bg-white p-5 rounded z-10 border border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">Order Summary</h2>

              <div className="mt-4">
                <span className="text-gray-700 text-sm">Items ({cart.length}):</span>
                <span className="float-right text-gray-900 text-sm font-bold">${currentTotal}</span>
              </div>
              <div className="mt-2 text-red-700 font-bold text-lg border-t pt-2 border-gray-100">
                Order total: <span className="float-right">${currentTotal}</span>
              </div>

              {paymentSuccess ? (
                <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded text-center">
                  <h3 className="text-green-800 font-bold text-lg mb-1">Payment Successful!</h3>
                  <p className="text-sm text-green-700">Webhook sent to Django. Check MS Dashboard below.</p>
                </div>
              ) : (
                <div className="mt-6">
                  {cart.length > 0 ? (
                    <Elements stripe={stripePromise}>
                      <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">Payment Details</span>
                      <CheckoutForm cart={cart} onPaymentSuccess={() => { setCart([]); setPaymentSuccess(true); }} />
                    </Elements>
                  ) : (
                    <div className="p-4 bg-gray-50 text-center text-sm text-gray-500 border border-dashed rounded mt-4">
                      Add items to cart to checkout
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Microservice Live Dashboard */}
            <div className="bg-white p-5 rounded z-10 border border-gray-200">
              <h2 className="text-lg font-bold text-gray-900 mb-2">Microservice Dashboard</h2>
              <p className="text-xs text-gray-500 mb-4 leading-tight">
                Polling V2 API. When the webhook hits Django, it writes to Kafka. FastAPI consumes it here.
              </p>

              <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                <AnimatePresence>
                  {orders.slice().reverse().map(order => (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      key={order.id}
                      className="p-3 bg-gray-50 border border-gray-200 rounded"
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-xs font-bold text-gray-700">Order {order.id}</span>
                        {order.status === 'PENDING' ? (
                          <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-800 text-[10px] font-bold rounded">PENDING</span>
                        ) : order.status === 'PAID' ? (
                          <span className="px-1.5 py-0.5 bg-green-100 text-green-800 text-[10px] font-bold rounded">PAID</span>
                        ) : (
                          <span className="px-1.5 py-0.5 bg-gray-200 text-gray-800 text-[10px] font-bold rounded">{order.status}</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-600">Sync: {new Date(order.created_at).toLocaleTimeString()}</div>
                    </motion.div>
                  ))}
                  {orders.length === 0 && (
                    <div className="text-center text-sm text-gray-500 py-4 italic">No orders yet.</div>
                  )}
                </AnimatePresence>
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}
