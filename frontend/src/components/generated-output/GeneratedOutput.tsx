import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from '@carbon/icons-react'
import { useDownload } from '../../hooks/useDownload'
import './GeneratedOutput.css'

interface GeneratedOutputProps {
  llmsTxt: string
}

function GeneratedOutput({ llmsTxt }: GeneratedOutputProps) {
  const navigate = useNavigate()
  const handleDownload = useDownload(llmsTxt, 'llms.txt')

  function handleCopy() {
    navigator.clipboard.writeText(llmsTxt)
  }

  return (
    <section className="generated-output-container">
      <button className="generated-output-back" onClick={() => navigate('/')}>
        <ArrowLeft /> Back to home
      </button>
      <div className="generated-output-code">
        <div className="generated-output-code-header">
          <span>llms.txt</span>
          <div className="generated-output-actions">
            <button className="generated-output-action-btn" onClick={handleCopy}>
              Copy
            </button>
            <button className="generated-output-action-btn" onClick={handleDownload}>
              Download
            </button>
          </div>
        </div>
        <pre className="generated-output-content">{llmsTxt}</pre>
      </div>
    </section>
  )
}

export default GeneratedOutput
