import { Client } from 'pg';

const client = new Client();

export async function getUserById(userId: string) {
  // VULNERABLE: SQL Injection via string concatenation
  const query = `SELECT * FROM users WHERE id = '${userId}'`;
  const res = await client.query(query);
  return res.rows[0];
}
