import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ApplicationsListPage from "./pages/ApplicationsListPage";
import NewApplicationPage from "./pages/NewApplicationPage";
import ApplicationDetailPage from "./pages/ApplicationDetailPage";
import LendersListPage from "./pages/LendersListPage";
import LenderDetailPage from "./pages/LenderDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/applications" replace />} />
        <Route path="/applications" element={<ApplicationsListPage />} />
        <Route path="/applications/new" element={<NewApplicationPage />} />
        <Route path="/applications/:id" element={<ApplicationDetailPage />} />
        <Route path="/lenders" element={<LendersListPage />} />
        <Route path="/lenders/:id" element={<LenderDetailPage />} />
        <Route path="*" element={<Navigate to="/applications" replace />} />
      </Route>
    </Routes>
  );
}
