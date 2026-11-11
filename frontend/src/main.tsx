import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import "./theme.css";
import { applyTheme, initialTheme } from "./theme";

applyTheme(initialTheme());

createRoot(document.getElementById("root")!).render(<App />);
