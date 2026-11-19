document.querySelectorAll('[data-job-rating-width]').forEach(stars => {
  const width = Number(stars.dataset.jobRatingWidth);
  stars.style.width = (Number.isFinite(width) ? Math.max(0, Math.min(100, width)) : 0) + '%';
});
