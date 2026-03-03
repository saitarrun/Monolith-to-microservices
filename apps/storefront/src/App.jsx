import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShoppingCart, Package, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// API Configuration
const apiClient = axios.create({
  baseURL: 'http://localhost/api', // Maps to ingress root when dockerized
});

const products = [
  { id: 'prod-123', name: 'Premium Wireless Headphones', price: 299.99, image: '🎧' },
  { id: 'prod-456', name: 'Mechanical Keyboard (Cherry MX)', price: 149.99, image: '⌨️' },
  { id: 'prod-789', name: 'Ergonomic Office Chair', price: 499.99, image: '🪑' },
];

export default function App() {
  const [cart, setCart] = useState([]);
  const [orders, setOrders] = useState([]);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  // Poll Orders from V2 Microservice
  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const res = await apiClient.get('/v2/orders/');
        setOrders(res.data);
      } catch (err) {
        console.error("Failed to fetch orders (is backend running?)", err);
      }
    };
    fetchOrders(); // Initial fetch
    const interval = setInterval(fetchOrders, 2000); // Poll every 2s to show async state changes
    return () => clearInterval(interval);
  }, []);

  const addToCart = (product) => {
    setCart((prev) => [...prev, product]);
  };

  const checkout = async () => {
    if (cart.length === 0) return;
    setIsCheckingOut(true);

    // Send order to Monolith (V1 API)
    try {
      const orderData = {
        user_id: Math.floor(Math.random() * 1000), // Mock User
        product_id: cart[0].id,
        amount: cart.reduce((sum, item) => sum + item.price, 0),
        status: 'PENDING'
      };

      await apiClient.post('/v1/orders/', orderData);
      setCart([]); // Clear cart

      // The backend dual-writes to Kafka, the microservice picks it up. 
      // Our polling will catch it shortly!
    } catch (err) {
      console.error("Checkout failed:", err);
      alert("Failed to checkout. Ensure Monolith backend is running and CORS is configured.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <div className="min-h-screen font-sans">
      {/* Navbar */}
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center gap-2">
              <Package className="h-8 w-8 text-blue-600" />
              <span className="font-bold text-xl text-gray-900 tracking-tight">Event-Driven Store</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="relative p-2 text-gray-600 hover:text-blue-600 transition-colors">
                <ShoppingCart className="h-6 w-6" />
                {cart.length > 0 && (
                  <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-500 rounded-full">
                    {cart.length}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Main Product Catalog */}
          <div className="lg:col-span-2 space-y-6">
            <h2 className="text-2xl font-semibold text-gray-900">Featured Products</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {products.map((p) => (
                <motion.div
                  whileHover={{ y: -4 }}
                  key={p.id}
                  className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-all"
                >
                  <div className="h-48 bg-gray-50 flex items-center justify-center text-7xl">
                    {p.image}
                  </div>
                  <div className="p-5">
                    <h3 className="font-semibold text-gray-900 mb-1">{p.name}</h3>
                    <div className="flex justify-between items-center mt-4">
                      <span className="text-xl font-bold text-gray-900">${p.price}</span>
                      <button
                        onClick={() => addToCart(p)}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                      >
                        Add to Cart
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Sidebar (Cart & Orders Dashboard) */}
          <div className="space-y-6">

            {/* Cart Section */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2 mb-4">
                <ShoppingCart className="h-5 w-5" /> Current Cart
              </h2>

              {cart.length === 0 ? (
                <p className="text-gray-500 text-sm">Your cart is empty.</p>
              ) : (
                <div className="space-y-4 mb-6">
                  {cart.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-sm border-b border-gray-50 pb-2">
                      <span className="text-gray-700">{item.image} {item.name}</span>
                      <span className="font-medium">${item.price}</span>
                    </div>
                  ))}
                  <div className="flex justify-between items-center font-bold text-gray-900 pt-2 border-t border-gray-100">
                    <span>Total</span>
                    <span>${cart.reduce((s, i) => s + i.price, 0).toFixed(2)}</span>
                  </div>
                </div>
              )}

              <button
                onClick={checkout}
                disabled={cart.length === 0 || isCheckingOut}
                className="w-full py-3 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-semibold transition-colors flex justify-center items-center"
              >
                {isCheckingOut ? (
                  <span className="flex items-center gap-2">
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                      <Clock className="w-5 h-5" />
                    </motion.div>
                    Processing via Monolith...
                  </span>
                ) : 'Checkout (Submit to Monolith)'}
              </button>
            </div>

            {/* Orders Status Dashboard */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4 flex justify-between items-center">
                Live Orders
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full font-medium">
                  Polling Microservice
                </span>
              </h2>

              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                <AnimatePresence>
                  {orders.slice().reverse().map(order => (
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      key={order.id}
                      className="p-3 bg-gray-50 border border-gray-100 rounded-lg"
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-xs text-gray-500 font-mono">Order #{order.id} / MS ID: {order.original_id}</span>
                        {order.status === 'PENDING' ? (
                          <span className="flex items-center gap-1 text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                            <Clock className="w-3 h-3" /> Pending
                          </span>
                        ) : order.status === 'COMPLETED' ? (
                          <span className="flex items-center gap-1 text-xs font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full border border-green-200">
                            <CheckCircle2 className="w-3 h-3" /> Completed
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded-full border border-red-200">
                            <AlertCircle className="w-3 h-3" /> {order.status}
                          </span>
                        )}
                      </div>
                      <div className="font-medium text-gray-900 text-sm">
                        Product: {order.product_id}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        Kafka Sync: {new Date(order.created_at).toLocaleTimeString()}
                      </div>
                    </motion.div>
                  ))}
                  {orders.length === 0 && (
                    <div className="text-center text-sm text-gray-500 py-4">
                      No orders replicated to microservice yet.
                    </div>
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
