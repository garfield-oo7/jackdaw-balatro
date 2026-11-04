//! Resets per second of one Gym env: `reset`, then the observation and the action mask, as a
//! vector env runs them at an episode's end.
//!
//! `cargo run --release -p jackdaw-env --example resets [n] [--verify]`

use std::hash::{DefaultHasher, Hash, Hasher};
use std::time::Instant;

use jackdaw_core::run::RunSpec;
use jackdaw_env::env::{EnvConfig, GYM_OBS_LEN, GymEnv};
use jackdaw_env::gym::MAX_ACTIONS;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn spec(i: u64) -> RunSpec {
    RunSpec {
        back: jackdaw_core::card::center_by_key("b_red").unwrap(),
        stake: 1,
        seed: format!("ROLL{i:04}"),
        challenge: None,
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let verify = args.iter().any(|a| a == "--verify");
    let n: u64 = args
        .iter()
        .find(|a| !a.starts_with("--"))
        .map_or(100_000, |s| s.parse().expect("resets"));
    let mut hasher = DefaultHasher::new();
    let mut env = GymEnv::new(&spec(0), EnvConfig::default(), 1).unwrap();
    let mut obs = vec![0f32; GYM_OBS_LEN];
    let mut mask = vec![0u8; MAX_ACTIONS];
    let mut checksum = 0f64;
    let start = Instant::now();
    for i in 0..n {
        env.reset(&spec(i), None).unwrap();
        env.write_obs(&mut obs);
        env.write_action_mask(&mut mask);
        checksum += f64::from(obs[0]) + f64::from(mask[0]);
        if verify {
            for x in &obs {
                x.to_bits().hash(&mut hasher);
            }
            mask.hash(&mut hasher);
            env.table().actions().hash(&mut hasher);
            jackdaw_core::canon::digest(&env.game().snapshot()).hash(&mut hasher);
        }
    }
    if verify {
        println!("verify hash {:016x}", hasher.finish());
    }
    let secs = start.elapsed().as_secs_f64();
    println!(
        "{n} resets in {secs:.3} s: {:.3} us/reset, checksum {checksum}",
        secs * 1e6 / n as f64
    );
}
