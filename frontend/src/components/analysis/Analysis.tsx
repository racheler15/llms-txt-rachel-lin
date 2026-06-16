import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { recentScansQueryKey } from '../../hooks/useRecentScans'
import { useMarkViewed } from '../../hooks/useMarkViewed'
import { useRecrawl } from '../../hooks/useRecrawl'
import { useScan } from '../../hooks/useScan'
import AnalysisOverview from './analysis-overview/AnalysisOverview'
import CategoriesBreakdown from './categories-breakdown/CategoriesBreakdown'
import { extractHostnameFromLlmsTxt, formatScannedLabel, parseLlmsTxtStats } from './analysisUtils'
import GeneratedOutput from './generated-output/GeneratedOutput'
import ReadinessScore from './readiness-score/ReadinessScore'
import './Analysis.css'

function Analysis() {
  const { domain: domainParam } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const markedViewedRef = useRef(false)
  const { data: analysis, isLoading, isError, error, isFetching } = useScan(domainParam)
  const { mutateAsync: markViewed } = useMarkViewed(domainParam)
  const { mutateAsync: recrawl, isPending: isRescanning } = useRecrawl(domainParam)

  useEffect(() => {
    if (!domainParam) {
      navigate('/')
    }
  }, [domainParam, navigate])

  useEffect(() => {
    markedViewedRef.current = false
  }, [domainParam])

  useEffect(() => {
    if (!analysis || markedViewedRef.current || !domainParam) {
      return
    }

    markedViewedRef.current = true
    markViewed().catch(() => {
      markedViewedRef.current = false
    })
  }, [analysis, domainParam, markViewed])

  if (!domainParam) {
    return null
  }

  if (isLoading) {
    return <p className="analysis-loading">Loading analysis...</p>
  }

  if (!analysis) {
    if (isError) {
      return (
        <section className="analysis-error">
          <p>{error?.message ?? 'Unable to load analysis.'}</p>
          <button type="button" onClick={() => navigate('/')}>
            Back to home
          </button>
        </section>
      )
    }
    return null
  }

  const llmsTxt = analysis.llmsTxt
  const llmsStats = llmsTxt ? parseLlmsTxtStats(llmsTxt) : null
  const categoryCount = llmsStats?.categoryCount ?? 0
  const parsedPagesIncluded = llmsStats?.pagesIncluded ?? analysis.pagesIncluded
  const scannedLabel = analysis.lastScannedAt
    ? formatScannedLabel(analysis.lastScannedAt)
    : 'scanned just now'

  async function handleRescan() {
    await recrawl()
    queryClient.invalidateQueries({ queryKey: recentScansQueryKey })
  }

  return (
    <>
      <AnalysisOverview
        domain={analysis.domain || domainParam || extractHostnameFromLlmsTxt(llmsTxt ?? '')}
        pagesCrawled={analysis.pagesCrawled}
        pagesIncluded={analysis.pagesIncluded ?? parsedPagesIncluded}
        categoryCount={categoryCount}
        aiReadiness={analysis.readiness?.total}
        scannedLabel={scannedLabel}
        isRescanning={isRescanning || isFetching}
        onRescan={handleRescan}
      />
      {analysis.readiness && <ReadinessScore readiness={analysis.readiness} />}
      {llmsTxt && <CategoriesBreakdown llmsTxt={llmsTxt} />}
      {llmsTxt ? (
        <GeneratedOutput llmsTxt={llmsTxt} />
      ) : (
        <section className="analysis-missing-output">
          <p>No llms.txt has been generated for this domain yet.</p>
          <button type="button" onClick={() => navigate('/')}>
            Generate from homepage
          </button>
        </section>
      )}
    </>
  )
}

export default Analysis
