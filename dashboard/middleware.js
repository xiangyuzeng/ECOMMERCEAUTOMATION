import { NextResponse } from 'next/server';

export async function middleware(request) {
  const { pathname } = request.nextUrl;

  // Skip for non-root paths
  if (
    pathname !== '/' ||
    pathname.startsWith('/setup') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/_next')
  ) {
    return NextResponse.next();
  }

  // Check setup state via internal API call
  try {
    const baseUrl = request.nextUrl.origin;
    const res = await fetch(`${baseUrl}/api/setup`, {
      headers: { 'x-middleware-check': '1' },
    });
    const data = await res.json();

    if (!data.configured) {
      return NextResponse.redirect(new URL('/setup', request.url));
    }
  } catch {
    // If API fails, don't block — let the user through
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/'],
};
