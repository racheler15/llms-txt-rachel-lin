export function useDownload(content: string, filename: string) {
  function download() {
    const blob = new Blob([content], { type: 'text/plain' })
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    a.click()
    URL.revokeObjectURL(href)
  }

  return download
}
