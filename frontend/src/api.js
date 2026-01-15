import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const sendMessage = async (message, token) => {
  const response = await api.post('/chat', {
    message: message,
  }, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.data;
};
