"use strict";

const DEFAULT_SOURCE = process.env.PRICE_SOURCE || "MARK_PRICE";

const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());

// DigitalOcean: use sempre process.env.PORT (e fallback 8080)
const PORT = parseInt(process.env.PORT || "8080", 10);

// Data dir padrão (fallback local)
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");

// Links (Spaces) – se existirem, a API lê direto de lá
const PRO_JSON_URL = process.env.PRO_JSON_URL || "";
const TOP10_JSON_URL = process.env.TOP10_JSON_URL || "";

// Cache simples em memória (evita buscar toda hora)
