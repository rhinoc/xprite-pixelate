//! Sequential stand-in for `rayon::join`: runs `a`, then `b`.

pub fn join<A, B, RA, RB>(a: A, b: B) -> (RA, RB)
where
    A: FnOnce() -> RA,
    B: FnOnce() -> RB,
{
    let ra = a();
    let rb = b();
    (ra, rb)
}
