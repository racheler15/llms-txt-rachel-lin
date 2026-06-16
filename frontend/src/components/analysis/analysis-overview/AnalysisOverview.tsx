import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Renew } from '@carbon/icons-react'
import StatCards, { type StatItem } from './stat-cards/StatCards'
import './AnalysisOverview.css'

interface AnalysisOverviewProps {
  domain: string
  pagesCrawled?: number
  pagesIncluded: number
  categoryCount: number
  aiReadiness?: number
  scannedLabel?: string
  isRescanning?: boolean
  onRescan?: () => void
}

function formatStat(value: number | undefined): string {
  return value != null ? String(value) : 'N/A'
}

function AnalysisOverview({
  domain,
  pagesCrawled,
  pagesIncluded,
  categoryCount,
  aiReadiness,
  scannedLabel = 'scanned just now',
  isRescanning = false,
  onRescan,
}: AnalysisOverviewProps) {
  const navigate = useNavigate()

  const stats: StatItem[] = [
    { label: 'Pages crawled', value: formatStat(pagesCrawled) },
    { label: 'Pages included', value: String(pagesIncluded) },
    { label: 'Categories', value: String(categoryCount) },
    { label: 'AI readiness', value: aiReadiness != null ? `${aiReadiness}/100` : 'N/A', variant: 'accent' },
  ]

  return (
    <section className="analysis-overview-container">
      <button className="analysis-overview-back" onClick={() => navigate('/')}>
        <ArrowLeft size={16} />
        Back to home
      </button>

      <div className="analysis-overview-header">
        <div className="analysis-overview-title-row">
          <div className="analysis-overview-site-info">
            <div className="analysis-overview-domain-row">
              <h1 className="analysis-overview-domain">{domain}</h1>
            </div>
            <p className="analysis-overview-meta">
              {pagesCrawled != null ? `${pagesCrawled} pages · ` : ''}
              {scannedLabel}
            </p>
          </div>
          <button
            className="analysis-overview-refresh"
            onClick={onRescan}
            type="button"
            disabled={!onRescan || isRescanning}
          >
            <Renew size={16} />
            {isRescanning ? 'Rescanning...' : 'Rescan'}
          </button>
        </div>
      </div>

      <StatCards stats={stats} />
    </section>
  )
}

export default AnalysisOverview
