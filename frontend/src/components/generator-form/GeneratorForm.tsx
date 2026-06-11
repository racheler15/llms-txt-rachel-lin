import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGenerate } from '../../hooks/useGenerate'
import './GeneratorForm.css'

function GeneratorForm() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()
  const { mutateAsync, isPending, isError, error } = useGenerate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const llmsTxt = await mutateAsync(url)
    navigate('/analysis', { state: { llmsTxt } })
  }

  return (
    <section className="generator-container">
      <h1 className="generator-heading">Make your site AI-ready</h1>
      <p className="generator-subtitle">
        Generate a spec-compliant llms.txt file for any website.
      </p>

      <form className="generator-form" onSubmit={handleSubmit} noValidate>
        <input
          type="url"
          placeholder="https://yoursite.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <button type="submit" disabled={isPending}>
          {isPending ? 'Generating...' : 'Generate'}
        </button>
      </form>

      {isError && <p className="generator-error">{error?.message ?? 'Something went wrong. Please try again.'}</p>}
    </section>
  )
}

export default GeneratorForm
