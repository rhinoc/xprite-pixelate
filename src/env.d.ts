/**
 * The two platform names the sources use. Browsers and Node both provide them; the package keeps
 * `lib` free of DOM and Node types so neither platform's API leaks into the algorithm.
 */
interface ImportMeta {
  readonly url: string;
}

declare class URL {
  constructor(url: string, base?: string | URL);
  readonly href: string;
  readonly pathname: string;
  readonly protocol: string;
}
