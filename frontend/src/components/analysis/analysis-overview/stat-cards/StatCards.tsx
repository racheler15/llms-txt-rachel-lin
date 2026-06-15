import './StatCards.css'

export interface StatItem {
  label: string
  value: string
  variant?: 'default' | 'accent'
}

interface StatCardsProps {
  stats: StatItem[]
}

function StatCards({ stats }: StatCardsProps) {
  return (
    <div className="stat-cards">
      {stats.map((stat) => (
        <div key={stat.label} className="stat-card">
          <span className="stat-card-label">{stat.label}</span>
          <span className={`stat-card-value${stat.variant === 'accent' ? ' stat-card-value--accent' : ''}`}>
            {stat.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default StatCards
