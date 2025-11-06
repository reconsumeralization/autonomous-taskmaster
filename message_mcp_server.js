// region Message Relay MCP Server
// INPUT: text (str), from (str) for send_message; none for get_messages
// OUTPUT: send_message returns status, text, from; get_messages returns all messages

const { createServer } = require('@modelcontextprotocol/server-sequential-thinking');
let messages = [];
const server = createServer();

server.tool('send_message', async ({ text, from }) => {
  messages.push({ text, from, time: Date.now() });
  return { status: 'sent', text, from };
});

server.tool('get_messages', async () => {
  return { messages };
});

server.listen();
// endregion Message Relay MCP Server 