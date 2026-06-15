import type { ReadinessResult } from '../../../hooks/useGenerate'
import './ReadinessScore.css'

interface ReadinessScoreProps {
  readiness: ReadinessResult
}

function barColorClass(score: number, maxScore: number): string {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0
  if (pct >= 75) return 'readiness-dimension-bar-fill--green'
  if (pct >= 50) return 'readiness-dimension-bar-fill--amber'
  return 'readiness-dimension-bar-fill--red'
}

function ReadinessScore({ readiness }: ReadinessScoreProps) {
  return (
    <section className="readiness-score-card">
      <h2 className="readiness-score-title">Website AI readiness score</h2>

      <div className="readiness-score-dimensions">
        {readiness.categories.map((category) => {
          const pct = category.max_score > 0 ? (category.score / category.max_score) * 100 : 0

          return (
            <div key={category.id} className="readiness-dimension">
              <div className="readiness-dimension-header">
                <span className="readiness-dimension-label">{category.label}</span>
                <span className="readiness-dimension-score">
                  {category.score}/{category.max_score}
                </span>
              </div>
              <div className="readiness-dimension-bar-track">
                <div
                  className={`readiness-dimension-bar-fill ${barColorClass(category.score, category.max_score)}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {readiness.recommendations.length > 0 && (
        <div className="readiness-recommendations">
          <h3 className="readiness-recommendations-title">Recommendations</h3>
          <ul className="readiness-recommendations-list">
            {readiness.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default ReadinessScore
