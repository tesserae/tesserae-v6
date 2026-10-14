// Test responses for the fetch mocks. The shared request helper in
// src/utils/api.js reads the status and the body text first, so a mocked
// response needs `ok` and `text()` as well as `json()`. `mockResponse` fills in what
// a test left out: success by default, and a text body made from json().
export const mockResponse = (response) => ({
  ok: true,
  status: 200,
  ...response,
  text: response.text || (async () => JSON.stringify(await response.json())),
});
