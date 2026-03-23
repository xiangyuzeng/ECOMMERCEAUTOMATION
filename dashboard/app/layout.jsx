import './globals.css';

export const metadata = {
  title: '肯葳科技亚马逊自动运营系统',
  description: '肯葳科技 AI 驱动的亚马逊自动运营分析系统',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
