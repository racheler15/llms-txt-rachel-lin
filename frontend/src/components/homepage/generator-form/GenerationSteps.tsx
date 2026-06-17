import { CheckmarkFilled, CircleDash } from '@carbon/icons-react'
import { GENERATION_STEPS, type GenerateProgress } from '../../../types/generation'
import './GenerationSteps.css'

interface GenerationStepsProps {
  progress: GenerateProgress
}

function GenerationSteps({ progress }: GenerationStepsProps) {
  const activeIndex = GENERATION_STEPS.findIndex((step) => step.id === progress.step)

  return (
    <ol className="generation-steps" aria-label="Generation progress">
      {GENERATION_STEPS.map((step, index) => {
        const status =
          index < activeIndex ? 'complete' : index === activeIndex ? 'active' : 'pending'

        return (
          <li key={step.id} className={`generation-step generation-step--${status}`}>
            <span className="generation-step-icon" aria-hidden="true">
              {status === 'complete' ? (
                <CheckmarkFilled size={16} />
              ) : (
                <CircleDash size={16} />
              )}
            </span>
            <span className="generation-step-label">
              {step.label}
              {step.id === 'crawling' && status === 'active' && progress.pagesCrawled != null && (
                <span className="generation-step-detail">{` — ${progress.pagesCrawled} pages found`}</span>
              )}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default GenerationSteps
