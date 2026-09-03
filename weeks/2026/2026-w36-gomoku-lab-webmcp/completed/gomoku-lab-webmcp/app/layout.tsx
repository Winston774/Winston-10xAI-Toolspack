import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Gomoku Lab — WebMCP Agent Demo',
  description: 'ChatGPT 外部模型透過 WebMCP 讀取、分析並操作即時五子棋棋盤。',
  openGraph: {
    title: 'Gomoku Lab — WebMCP Agent Demo',
    description: 'ChatGPT 外部模型透過 WebMCP 讀取、分析並操作即時五子棋棋盤。',
    images: ['https://gomoku-lab-webmcp-agent-demo.noisewinston.chatgpt.site/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Gomoku Lab — WebMCP Agent Demo',
    description: 'ChatGPT 外部模型透過 WebMCP 讀取、分析並操作即時五子棋棋盤。',
    images: ['https://gomoku-lab-webmcp-agent-demo.noisewinston.chatgpt.site/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
