import { useLocation, useNavigate } from 'react-router-dom'
import GeneratedOutput from '../components/generated-output/GeneratedOutput'

function AnalysisPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { llmsTxt } = (location.state as { llmsTxt: string }) || {}

  if (!llmsTxt) {
    navigate('/')
    return null
  }

  return <GeneratedOutput llmsTxt={llmsTxt} />
}

export default AnalysisPage
