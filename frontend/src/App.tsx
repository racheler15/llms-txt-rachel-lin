import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Navbar from './components/navbar/Navbar'
import HomePage from './pages/Homepage'
import AnalysisPage from './pages/AnalysisPage'

const queryClient = new QueryClient()

function Layout() {
  return (
    <div className="app-shell">
      <Navbar />
      <Outlet />
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/analysis/:domain" element={<AnalysisPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
