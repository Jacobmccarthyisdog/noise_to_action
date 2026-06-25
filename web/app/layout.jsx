import './globals.css';
import './harbor-refresh.css';

export const metadata = {
  title: 'From Noise to Action | Alpine Ops Signal Ledger',
  description: 'Alpine Ops-styled benchmark-relative portfolio field ledger',
};

export default function RootLayout({ children }) {
  return (
    <html lang='en'>
      <body>{children}</body>
    </html>
  );
}
