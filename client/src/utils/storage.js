export const getSessionValue = (key, defaultVal) => {
  try {
    const stored = sessionStorage.getItem('tesserae_' + key);
    return stored !== null ? stored : defaultVal;
  } catch (e) {
    return defaultVal;
  }
};

export const setSessionValue = (key, value) => {
  try {
    sessionStorage.setItem('tesserae_' + key, value);
  } catch (e) {}
};
