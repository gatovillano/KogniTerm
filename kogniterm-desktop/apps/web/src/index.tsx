import { render } from "solid-js/web";
import { App } from "./App";
import "./index.css";
import { initTheme } from "./lib/theme";

initTheme();

render(() => <App />, document.getElementById("root")!);
