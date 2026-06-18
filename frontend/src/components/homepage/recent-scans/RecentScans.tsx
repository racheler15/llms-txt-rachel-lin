import { Link } from 'react-router-dom'
import { formatScannedLabel } from '../../analysis/analysisUtils'
import { useRecentScans } from '../../../hooks/useRecentScans'
import './RecentScans.css'

function RecentScans() {
  const { data: scans, isLoading, isError } = useRecentScans()

  if (isLoading) {
    return (
      <section className="recent-scans">
        <h2 className="recent-scans-heading">Recent</h2>
        <p className="recent-scans-status">Loading...</p>
      </section>
    )
  }

  if (isError) {
    return (
      <section className="recent-scans">
        <h2 className="recent-scans-heading">Recent</h2>
        <p className="recent-scans-status">Unable to load recent files.</p>
      </section>
    )
  }

  if (!scans?.length) {
    return (
      <section className="recent-scans">
        <h2 className="recent-scans-heading">Recent</h2>
        <p className="recent-scans-status">No recently generated files.</p>
      </section>
    )
  }

  return (
    <section className="recent-scans">
      <h2 className="recent-scans-heading">Recent</h2>
      <ul className="recent-scans-list">
        {scans.map((scan) => (
          <li key={scan.domain}>
            <Link className="recent-scans-item" to={`/analysis/${scan.domain}`}>
              <div className="recent-scans-item-main">
                <span className="recent-scans-domain">{scan.domain}</span>
                {scan.hasUnviewedChanges && <span className="recent-scans-updated">Updated</span>}
              </div>
              <div className="recent-scans-item-meta">
                <span>{scan.pagesCrawled} pages crawled</span>
                <span>·</span>
                <span>{scan.readinessTotal}/100 AI readiness</span>
                <span>·</span>
                <span>{formatScannedLabel(scan.lastScannedAt)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default RecentScans
