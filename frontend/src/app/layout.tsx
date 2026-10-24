import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import ClientInitializer from './ClientInitializer';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'Cognexa AI - Autonomous Cognitive Engine & Memory System',
  description:
    'Advanced full-stack AI research and engineering agent platform featuring hierarchical memory, dynamic planning, and publication artifact synthesis.',
  keywords: ['AI', 'Agent', 'LangGraph', 'Memory', 'Autonomous', 'Cognexa'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.className} bg-[#f8f9fc] dark:bg-[#0b0c14] text-slate-800 dark:text-slate-100 min-h-screen antialiased selection:bg-purple-500/20`}
        suppressHydrationWarning
      >
        <ClientInitializer />
        {children}
      </body>
    </html>
  );
}
