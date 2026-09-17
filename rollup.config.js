// Decky provides an official rollup preset. It sets the externals, the
// global names Decky injects (SP_REACT, DFL, DFLAPI and friends), the
// output format and the plugin asset path.
//
// Do not hand-roll this. The global that @decky/api is exposed under is an
// implementation detail of the loader and has changed between versions;
// guessing it produces a bundle that builds cleanly and then throws
// "DFLAPI is not defined" at load time.
import deckyPlugin from "@decky/rollup";

export default deckyPlugin({});
