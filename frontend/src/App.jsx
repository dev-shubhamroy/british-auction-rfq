import { NavLink, Route, Routes } from 'react-router-dom'
import AuctionList from './pages/AuctionList'
import AuctionDetails from './pages/AuctionDetails'
import CreateRfq from './pages/CreateRfq'

function navClass({ isActive }) {
  return `px-3 py-1.5 rounded text-sm ${
    isActive ? 'bg-slate-100 text-slate-900 font-medium' : 'text-slate-600 hover:text-slate-900'
  }`
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <span className="font-semibold text-slate-900">RFQ Auctions</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navClass}>Auctions</NavLink>
            <NavLink to="/rfqs/new" className={navClass}>Create RFQ</NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<AuctionList />} />
          <Route path="/rfqs/new" element={<CreateRfq />} />
          <Route path="/rfqs/:id" element={<AuctionDetails />} />
        </Routes>
      </main>
    </div>
  )
}
