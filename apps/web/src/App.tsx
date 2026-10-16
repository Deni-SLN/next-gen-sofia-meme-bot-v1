import { createBrowserRouter } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Scanner from "./pages/Scanner";
import Tokens from "./pages/Tokens";
import Signals from "./pages/Signals";
import Watchlist from "./pages/Watchlist";
import Bot from "./pages/Bot";
import Orders from "./pages/Orders";
import Risk from "./pages/Risk";
import Portfolio from "./pages/Portfolio";
import Performance from "./pages/Performance";
import AiCenter from "./pages/AiCenter";
import Alerts from "./pages/Alerts";
import Wallet from "./pages/Wallet";
import Providers from "./pages/Providers";
import Settings from "./pages/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "scanner", element: <Scanner /> },
      { path: "tokens", element: <Tokens /> },
      { path: "tokens/:mint", element: <Tokens /> },
      { path: "signals", element: <Signals /> },
      { path: "watchlist", element: <Watchlist /> },
      { path: "analysis", element: <Signals /> },
      { path: "bot", element: <Bot /> },
      { path: "orders", element: <Orders /> },
      { path: "risk", element: <Risk /> },
      { path: "portfolio", element: <Portfolio /> },
      { path: "performance", element: <Performance /> },
      { path: "wallet", element: <Wallet /> },
      { path: "alerts", element: <Alerts /> },
      { path: "ai", element: <AiCenter /> },
      { path: "providers", element: <Providers /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);
