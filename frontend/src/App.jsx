import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Generate from "./pages/Generate";
// import Support from "./pages/Support";
import "./App.css";

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route element={<Layout />}>
                    <Route
                        path="/"
                        element={<Home />}
                    />
                    <Route
                        path="/generate"
                        element={<Generate />}
                    />
                    {/* <Route
                        path="/support"
                        element={<Support />}
                    /> */}
                </Route>
            </Routes>
        </BrowserRouter>
    );
}
