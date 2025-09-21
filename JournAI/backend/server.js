const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/journal', (req, res) => {
  res.json([{ id: 1, mood: 'happy', note: 'Good day!' }]);
});

app.listen(3000, () => console.log('Server running on port 3000'));
