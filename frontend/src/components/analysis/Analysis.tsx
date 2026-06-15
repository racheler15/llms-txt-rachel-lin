import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import type { ReadinessResult } from '../../hooks/useGenerate'
import AnalysisOverview from './analysis-overview/AnalysisOverview'
import { extractHostnameFromLlmsTxt, parseLlmsTxtStats } from './analysisUtils'
import GeneratedOutput from './generated-output/GeneratedOutput'
import ReadinessScore from './readiness-score/ReadinessScore'

function Analysis() {
  const location = useLocation()
  const navigate = useNavigate()
  const { llmsTxt, domain, pagesCrawled, pagesIncluded, readiness } =
    (location.state as {
      llmsTxt: string
      domain?: string
      pagesCrawled?: number
      pagesIncluded?: number
      readiness?: ReadinessResult
    }) || {}

  useEffect(() => {
    if (!llmsTxt) {
      navigate('/')
    }
  }, [llmsTxt, navigate])

  if (!llmsTxt) {
    return null
  }

  const { pagesIncluded: parsedPagesIncluded, categoryCount } = parseLlmsTxtStats(llmsTxt)

  return (
    <>
      <AnalysisOverview
        domain={domain || extractHostnameFromLlmsTxt(llmsTxt)}
        pagesCrawled={pagesCrawled}
        pagesIncluded={pagesIncluded ?? parsedPagesIncluded}
        categoryCount={categoryCount}
        aiReadiness={readiness?.total}
      />
      {readiness && <ReadinessScore readiness={readiness} />}
      <GeneratedOutput llmsTxt={llmsTxt} />
    </>
  )
}

export default Analysis
