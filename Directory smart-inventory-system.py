// Directory: smart-inventory-system

// == BACKEND: server/index.js ==
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const dotenv = require('dotenv');
const authRoutes = require('./routes/auth');
const inventoryRoutes = require('./routes/inventory');

dotenv.config();
const app = express();

app.use(cors());
app.use(express.json());

mongoose.connect(process.env.MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('MongoDB Connected'))
  .catch(err => console.log(err));

app.use('/api/auth', authRoutes);
app.use('/api/inventory', inventoryRoutes);

app.listen(5000, () => console.log('Server running on port 5000'));

// == BACKEND: server/models/User.js ==
const mongoose = require('mongoose');
const UserSchema = new mongoose.Schema({
  username: { type: String, required: true, unique: true },
  password: { type: String, required: true }
});
module.exports = mongoose.model('User', UserSchema);

// == BACKEND: server/models/Item.js ==
const mongoose = require('mongoose');
const ItemSchema = new mongoose.Schema({
  name: String,
  description: String,
  quantity: Number,
  imageUrl: String,
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User' }
});
module.exports = mongoose.model('Item', ItemSchema);

// == BACKEND: server/routes/auth.js ==
const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const User = require('../models/User');
const router = express.Router();

router.post('/register', async (req, res) => {
  const { username, password } = req.body;
  const hashed = await bcrypt.hash(password, 10);
  try {
    const user = new User({ username, password: hashed });
    await user.save();
    res.status(201).json({ message: 'User created' });
  } catch (err) {
    res.status(500).json(err);
  }
});

router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const user = await User.findOne({ username });
    if (!user || !await bcrypt.compare(password, user.password)) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }
    const token = jwt.sign({ id: user._id }, process.env.JWT_SECRET);
    res.json({ token });
  } catch (err) {
    res.status(500).json(err);
  }
});

module.exports = router;

// == BACKEND: server/routes/inventory.js ==
const express = require('express');
const jwt = require('jsonwebtoken');
const multer = require('multer');
const AWS = require('aws-sdk');
const Item = require('../models/Item');
const router = express.Router();

const s3 = new AWS.S3({
  accessKeyId: process.env.AWS_ACCESS_KEY,
  secretAccessKey: process.env.AWS_SECRET_KEY,
  region: process.env.AWS_REGION
});

const storage = multer.memoryStorage();
const upload = multer({ storage });

const authMiddleware = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ message: 'Unauthorized' });
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.userId = decoded.id;
    next();
  } catch {
    res.status(401).json({ message: 'Invalid token' });
  }
};

router.post('/', authMiddleware, upload.single('image'), async (req, res) => {
  const { name, description, quantity } = req.body;
  const file = req.file;
  const params = {
    Bucket: process.env.S3_BUCKET,
    Key: `${Date.now()}_${file.originalname}`,
    Body: file.buffer,
    ACL: 'public-read'
  };
  try {
    const s3Res = await s3.upload(params).promise();
    const item = new Item({
      name,
      description,
      quantity,
      imageUrl: s3Res.Location,
      userId: req.userId
    });
    await item.save();
    res.status(201).json(item);
  } catch (err) {
    res.status(500).json(err);
  }
});

router.get('/', authMiddleware, async (req, res) => {
  const items = await Item.find({ userId: req.userId });
  res.json(items);
});

module.exports = router;

// (Frontend React app will be added next)
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import axios from 'axios';
import './App.css';

const App = () => {
  const [items, setItems] = useState([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (token) {
      fetchItems();
    }
  }, [token]);

  const fetchItems = async () => {
    try {
      const response = await axios.get('http://localhost:5000/api/inventory', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      setItems(response.data);
    } catch (err) {
      console.error(err);
      setErrorMessage('Failed to fetch items');
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('http://localhost:5000/api/auth/login', {
        username,
        password,
      });
      setToken(response.data.token);
      setIsAuthenticated(true);
      setErrorMessage('');
    } catch (err) {
      setErrorMessage('Invalid credentials');
    }
  };

  const handleLogout = () => {
    setToken('');
    setIsAuthenticated(false);
  };

  return (
    <Router>
      <div className="App">
        <h1>Smart Inventory System</h1>

        {!isAuthenticated ? (
          <div>
            <form onSubmit={handleLogin}>
              <div>
                <input
                  type="text"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div>
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <button type="submit">Login</button>
            </form>
            {errorMessage && <p>{errorMessage}</p>}
          </div>
        ) : (
          <div>
            <button onClick={handleLogout}>Logout</button>
            <h2>Your Inventory</h2>
            {items.length === 0 ? (
              <p>No items found in your inventory.</p>
            ) : (
              <ul>
                {items.map((item) => (
                  <li key={item._id}>
                    <h3>{item.name}</h3>
                    <p>{item.description}</p>
                    <p>Quantity: {item.quantity}</p>
                    <img src={item.imageUrl} alt={item.name} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </Router>
  );
};

export default App;
import React, { useState } from 'react';
import axios from 'axios';

const Inventory = ({ token }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [quantity, setQuantity] = useState('');
  const [image, setImage] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const handleAddItem = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('quantity', quantity);
    formData.append('image', image);

    try {
      await axios.post('http://localhost:5000/api/inventory', formData, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      setName('');
      setDescription('');
      setQuantity('');
      setImage(null);
      setErrorMessage('');
    } catch (err) {
      setErrorMessage('Failed to add item');
    }
  };

  return (
    <div>
      <h2>Add New Item</h2>
      <form onSubmit={handleAddItem}>
        <div>
          <input
            type="text"
            placeholder="Item Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <textarea
            placeholder="Item Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
        </div>
        <div>
          <input
            type="number"
            placeholder="Quantity"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
        </div>
        <div>
          <input
            type="file"
            onChange={(e) => setImage(e.target.files[0])}
            required
          />
        </div>
        <button type="submit">Add Item</button>
      </form>
      {errorMessage && <p>{errorMessage}</p>}
    </div>
  );
};

export default Inventory;
import React from 'react';
import { Navigate } from 'react-router-dom';

const ProtectedRoute = ({ children, isAuthenticated }) => {
  return isAuthenticated ? children : <Navigate to="/" />;
};

export default ProtectedRoute;
import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import App from './App';

ReactDOM.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
  document.getElementById('root')
);
