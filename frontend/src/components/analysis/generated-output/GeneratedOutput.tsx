import { useDownload } from '../../../hooks/useDownload'
import './GeneratedOutput.css'

interface GeneratedOutputProps {
  llmsTxt: string
  domain: string
}

function GeneratedOutput({ llmsTxt, domain }: GeneratedOutputProps) {
  const filename = `${domain}.llms.txt`
  const handleDownload = useDownload(llmsTxt, filename)

  function handleCopy() {
    navigator.clipboard.writeText(llmsTxt)
  }

  return (
    <section className="generated-output-container">
      <div className="generated-output-code">
        <div className="generated-output-code-header">
          <span>{filename}</span>
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
