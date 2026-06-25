import Script from 'next/script';
import './globals.css';
import './harbor-refresh.css';
import './harbor-detail-cards.css';
import './harbor-lava.css';

export const metadata = {
  title: 'From Noise to Action | Alpine Ops Signal Ledger',
  description: 'Alpine Ops-styled benchmark-relative portfolio field ledger',
};

export default function RootLayout({ children }) {
  return (
    <html lang='en'>
      <body>
        <Script id='reset-scroll-position' strategy='beforeInteractive'>
          {`
            if ('scrollRestoration' in history) {
              history.scrollRestoration = 'manual';
            }
            window.scrollTo(0, 0);
            window.addEventListener('pageshow', function () {
              window.scrollTo(0, 0);
            });
            window.addEventListener('beforeunload', function () {
              window.scrollTo(0, 0);
            });
          `}
        </Script>
        {children}
      </body>
    </html>
  );
}
