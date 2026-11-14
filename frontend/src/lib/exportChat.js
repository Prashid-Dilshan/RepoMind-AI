const sourceLabel = (s) => {
  if (typeof s === 'string') return s;
  const lines = s.start_line ? ` (lines ${s.start_line}${s.end_line > s.start_line ? `-${s.end_line}` : ''})` : '';
  return s.url ? `[${s.path}${lines}](${s.url})` : `${s.path}${lines}`;
};

export function exportChat(repo, messages) {
  const lines = [`# Chat about ${repo.name}`, '', `Exported ${new Date().toLocaleString()}`, ''];
  for (const m of messages) {
    if (m.isError) continue;
    if (m.role === 'user') {
      lines.push('## Question', '', m.content, '');
    } else {
      lines.push('## Answer', '', m.content, '');
      if (m.sources?.length) {
        lines.push('Sources:', '');
        m.sources.forEach((s) => lines.push(`- ${sourceLabel(s)}`));
        lines.push('');
      }
    }
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${repo.name.replace(/[^\w.-]+/g, '-')}-chat.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
