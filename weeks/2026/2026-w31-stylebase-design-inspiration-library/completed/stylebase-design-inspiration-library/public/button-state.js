export function beginPendingButtons(buttons, label = "送交中…") {
  const snapshots = [...buttons]
    .filter(Boolean)
    .map((button) => ({
      button,
      disabled: button.disabled,
      innerHTML: button.innerHTML,
    }));

  for (const { button } of snapshots) {
    button.disabled = true;
    button.textContent = label;
  }

  return function restorePendingButtons() {
    for (const { button, disabled, innerHTML } of snapshots) {
      if (button.isConnected === false) continue;
      button.innerHTML = innerHTML;
      button.disabled = disabled;
    }
  };
}
