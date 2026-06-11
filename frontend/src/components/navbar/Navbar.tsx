import { Link } from 'react-router-dom'
import './Navbar.css'

function Navbar() {
  return (
    <nav className="navbar-container">
      <Link to="/" className="navbar-title">automated llms.txt generator</Link>
      <Link to="/" className="navbar-link">Home</Link>
    </nav>
  )
}

export default Navbar
