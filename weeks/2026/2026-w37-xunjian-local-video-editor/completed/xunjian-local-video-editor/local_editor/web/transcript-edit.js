import { mappedCaptions } from './utils.js';

export const transcriptRows = (project) => mappedCaptions(project);

export function selectedCharacters(text, start, end) {
  if (start === end) return null;
  return { start: Array.from(text.slice(0, start)).length,
    end: Array.from(text.slice(0, end)).length };
}

export function copyClips(project, selectedIds) {
  const clips = project.clips.filter(c => selectedIds.includes(c.id)).map(c => {
    const { id, ...value } = c;
    return structuredClone(value);
  });
  return clips.length ? { projectId: project.id, clips } : null;
}
