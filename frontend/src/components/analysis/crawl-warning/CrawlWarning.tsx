import { WarningAlt } from '@carbon/icons-react'
import './CrawlWarning.css'

function CrawlWarning() {
  return (
    <section className="crawl-warning" role="status">
      <WarningAlt size={20} className="crawl-warning-icon" aria-hidden="true" />
      <div>
        <p className="crawl-warning-title">Results may be incomplete</p>
        <p className="crawl-warning-text">
          This site appears to rely on JavaScript for much of its content. We crawl raw HTML
          only, so some pages may be missing or have limited metadata.
        </p>
      </div>
    </section>
  )
}

export default CrawlWarning
