import { useState } from 'react'
import { ChevronDown } from '@carbon/icons-react'
import { parseLlmsTxtCategories } from '../analysisUtils'
import './CategoriesBreakdown.css'

interface CategoriesBreakdownProps {
  llmsTxt: string
}

function CategoriesBreakdown({ llmsTxt }: CategoriesBreakdownProps) {
  const categories = parseLlmsTxtCategories(llmsTxt)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  if (!categories.length) {
    return null
  }

  function toggleCategory(name: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  return (
    <section className="categories-breakdown-card">
      <h2 className="categories-breakdown-title">Pages by category</h2>

      <div className="categories-breakdown-list">
        {categories.map((category) => {
          const isOpen = expanded.has(category.name)

          return (
            <div key={category.name} className="categories-breakdown-group">
              <button
                type="button"
                className="categories-breakdown-toggle"
                onClick={() => toggleCategory(category.name)}
                aria-expanded={isOpen}
              >
                <span className="categories-breakdown-toggle-main">
                  <ChevronDown
                    size={16}
                    className={`categories-breakdown-chevron${isOpen ? ' categories-breakdown-chevron--open' : ''}`}
                  />
                  <span className="categories-breakdown-name">{category.name}</span>
                </span>
                <span className="categories-breakdown-count">
                  {category.count} {category.count === 1 ? 'page' : 'pages'}
                </span>
              </button>

              {isOpen && category.links.length > 0 && (
                <ul className="categories-breakdown-links">
                  {category.links.map((link) => (
                    <li key={`${category.name}-${link.url}`}>
                      <a href={link.url} target="_blank" rel="noopener noreferrer">
                        {link.title}
                      </a>
                      {link.description && (
                        <span className="categories-breakdown-description">{link.description}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default CategoriesBreakdown
