// import { useEffect, useState } from "react";
import { useCallback, useEffect, useState } from "react";
import api from "./api";
import "./App.css";

export default function App() {
  const [mode, setMode] = useState("login");
  const [user, setUser] = useState(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [restaurants, setRestaurants] = useState([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [menu, setMenu] = useState([]);
  const [cart, setCart] = useState({});
  const [orders, setOrders] = useState([]);
  const [address, setAddress] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadRestaurants() {
    try {
      const response = await api.get("/restaurants/");
      const data = response.data;
      setRestaurants(Array.isArray(data) ? data : data.results || []);
    } catch {
      setError("Could not load restaurants. Check that Django is running.");
    }
  }

  async function loadMenu(restaurant) {
    setError("");
    setMessage("");
    setSelectedRestaurant(restaurant);
    setCart({});

    try {
      const response = await api.get("/menu-items/", {
        params: { restaurant_id: restaurant.id },
      });
      const data = response.data;
      setMenu(Array.isArray(data) ? data : data.results || []);
    } catch {
      setError("Could not load this restaurant's menu.");
    }
  }

  // async function loadOrders() {
  //   try {
  //     const response = await api.get("/orders/mine/");
  //     const data = response.data;
  //     setOrders(Array.isArray(data) ? data : data.results || []);
  //   } catch {
  //     setError("Could not load orders. Please log in again.");
  //   }
  // }
  const loadOrders = useCallback(async () => {
    if (!localStorage.getItem("foodflow_token")) return;

    try {
      const response = await api.get("/orders/mine/");
      const data = response.data;

      setOrders(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      console.error("Could not refresh orders:", err);
    }
  }, []);

  useEffect(() => {
    loadRestaurants();

    const token = localStorage.getItem("foodflow_token");
    const savedUser = localStorage.getItem("foodflow_user");

    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem("foodflow_user");
      }
    }
  }, []);

  useEffect(() => {
    if (!user) return;

    loadOrders();

    const intervalId = window.setInterval(() => {
      loadOrders();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [user, loadOrders]);

  async function submitAuth(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      if (mode === "register") {
        await api.post("/auth/register/", {
          username,
          email,
          password,
        });

        setMessage("Account created. You can now log in.");
        setMode("login");
      } else {
        const response = await api.post("/auth/login/", {
          username,
          password,
        });

        localStorage.setItem("foodflow_token", response.data.token);
        localStorage.setItem(
          "foodflow_user",
          JSON.stringify(response.data.user)
        );
        setUser(response.data.user);
        setMessage(`Welcome, ${response.data.user.username}!`);
      }
    } catch (err) {
      const data = err.response?.data;
      setError(
        typeof data === "object"
          ? Object.values(data).flat().join(" ")
          : "Authentication failed. Check your details and try again."
      );
    } finally {
      setLoading(false);
    }
  }

  function addToCart(item) {
    setCart((current) => ({
      ...current,
      [item.id]: {
        item,
        quantity: (current[item.id]?.quantity || 0) + 1,
      },
    }));
  }

  function changeQuantity(itemId, delta) {
    setCart((current) => {
      const existing = current[itemId];
      if (!existing) return current;

      const quantity = existing.quantity + delta;
      const next = { ...current };

      if (quantity <= 0) delete next[itemId];
      else next[itemId] = { ...existing, quantity };

      return next;
    });
  }

  const cartItems = Object.values(cart);
  const subtotal = cartItems.reduce(
    (sum, row) => sum + Number(row.item.price) * row.quantity,
    0
  );

  async function checkout() {
    if (!user) {
      setError("Please log in before placing an order.");
      setMode("login");
      return;
    }

    if (!selectedRestaurant || cartItems.length === 0 || !address.trim()) {
      setError("Choose menu items and enter a delivery address.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await api.post(
        "/orders/",
        {
          restaurant_id: selectedRestaurant.id,
          delivery_address: address.trim(),
          items: cartItems.map(({ item, quantity }) => ({
            menu_item_id: item.id,
            quantity,
          })),
        },
        {
          headers: {
            "Idempotency-Key": crypto.randomUUID(),
          },
        }
      );

      setMessage(`Order #${response.data.id} placed successfully.`);
      setCart({});
      await loadOrders();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Checkout failed. Check your connection and try again."
      );
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    try {
      await api.post("/auth/logout/");
    } catch {
      // Clear local state even if the server session has expired.
    }

    localStorage.removeItem("foodflow_token");
    localStorage.removeItem("foodflow_user");
    setUser(null);
    setOrders([]);
    setMessage("Logged out.");
  }

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>FoodFlow</h1>
          <p>Good food, delivered simply.</p>
        </div>

        {user ? (
          <div className="user-menu">
            <span>{user.username} · {user.role}</span>
            <button className="secondary" onClick={logout}>Log out</button>
          </div>
        ) : (
          <button onClick={() => setMode("login")}>Log in</button>
        )}
      </header>

      {(error || message) && (
        <div className={error ? "notice error" : "notice success"}>
          {error || message}
        </div>
      )}

      {!user && (
        <section className="panel auth-panel">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>

          <form onSubmit={submitAuth}>
            <label>
              Username
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                autoComplete="username"
              />
            </label>

            {mode === "register" && (
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoComplete="email"
                />
              </label>
            )}

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />
            </label>

            <button disabled={loading}>
              {loading
                ? "Please wait..."
                : mode === "login" ? "Log in" : "Register"}
            </button>
          </form>

          <p className="switch-mode">
            {mode === "login" ? "New to FoodFlow?" : "Already registered?"}
            {" "}
            <button
              className="text-button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
                setMessage("");
              }}
            >
              {mode === "login" ? "Create account" : "Log in"}
            </button>
          </p>
        </section>
      )}

      <section className="section">
        <div className="section-heading">
          <div>
            <h2>Restaurants</h2>
            <p>Choose a restaurant to explore its menu.</p>
          </div>
          <button className="secondary" onClick={loadRestaurants}>
            Refresh
          </button>
        </div>

        <div className="restaurant-grid">
          {restaurants.map((restaurant) => (
            <button
              className={
                selectedRestaurant?.id === restaurant.id
                  ? "restaurant-card selected"
                  : "restaurant-card"
              }
              key={restaurant.id}
              onClick={() => loadMenu(restaurant)}
            >
              <span className="restaurant-icon">🍽️</span>
              <strong>{restaurant.name}</strong>
              <span>{restaurant.address}</span>
              <small>{restaurant.description}</small>
            </button>
          ))}
        </div>
      </section>

      {selectedRestaurant && (
        <section className="section">
          <h2>{selectedRestaurant.name} menu</h2>

          <div className="menu-list">
            {menu.map((item) => (
              <article className="menu-item" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <p>{item.description}</p>
                  <span className="price">
                    Rs. {Number(item.price).toFixed(2)}
                  </span>
                </div>
                <button onClick={() => addToCart(item)}>Add</button>
              </article>
            ))}
            {menu.length === 0 && <p>No available menu items yet.</p>}
          </div>
        </section>
      )}

      {selectedRestaurant && (
        <section className="panel">
          <h2>Your cart</h2>

          {cartItems.length === 0 ? (
            <p>Your cart is empty.</p>
          ) : (
            <>
              {cartItems.map(({ item, quantity }) => (
                <div className="cart-row" key={item.id}>
                  <span>{item.name}</span>
                  <div className="quantity-controls">
                    <button className="secondary" onClick={() => changeQuantity(item.id, -1)}>
                      −
                    </button>
                    <span>{quantity}</span>
                    <button className="secondary" onClick={() => changeQuantity(item.id, 1)}>
                      +
                    </button>
                  </div>
                  <strong>
                    Rs. {(Number(item.price) * quantity).toFixed(2)}
                  </strong>
                </div>
              ))}

              <label>
                Delivery address
                <textarea
                  value={address}
                  onChange={(event) => setAddress(event.target.value)}
                  placeholder="Street, area, city..."
                  required
                />
              </label>

              <div className="total-row">
                <span>Subtotal</span>
                <strong>Rs. {subtotal.toFixed(2)}</strong>
              </div>
              <div className="total-row">
                <span>Delivery fee</span>
                <strong>Rs. 100.00</strong>
              </div>
              <div className="total-row grand-total">
                <span>Total (cash on delivery)</span>
                <strong>Rs. {(subtotal + 100).toFixed(2)}</strong>
              </div>

              <button disabled={loading} onClick={checkout}>
                {loading ? "Placing order..." : "Place order"}
              </button>
            </>
          )}
        </section>
      )}

      {user && (
        <section className="section">
          <div className="section-heading">
            <h2>Your orders</h2>
            <button className="secondary" onClick={loadOrders}>
              Refresh orders
            </button>
          </div>

          {orders.map((order) => (
            <article className="order-card" key={order.id}>
              <div className="section-heading">
                <strong>Order #{order.id}</strong>
                <span className="status">{order.status.replaceAll("_", " ")}</span>
              </div>
              <p>{order.restaurant_name}</p>
              <p>{order.delivery_address}</p>
              <p>Total: Rs. {Number(order.total).toFixed(2)}</p>
              <p>Rider: {order.rider_username || "Not assigned yet"}</p>
              <small>{new Date(order.created_at).toLocaleString()}</small>
            </article>
          ))}
          {order.rider_latitude != null &&
            order.rider_longitude != null &&
            ["ready", "picked_up"].includes(order.status) && (
              <p>
                <a
                  href={`https://www.openstreetmap.org/?mlat=${order.rider_latitude}&mlon=${order.rider_longitude}#map=16/${order.rider_latitude}/${order.rider_longitude}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View rider location on map
                </a>
              </p>
            )}

          {orders.length === 0 && (
            <p>No orders shown yet. Select a restaurant and place your first order.</p>
          )}
        </section>
      )}

      <footer>FoodFlow · Learning project</footer>
    </main>
  );
}
