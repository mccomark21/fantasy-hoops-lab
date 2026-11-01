// Team builder engine: the game counts of your core in the fantasy playoffs (issue #8, Rules and Contracts).
//
// The lineup-and-starts code is in core/starts.js (#213): scoreCore(), fit() and slotRoster(). This file adds the
// draft-only parts: footerWeeks() and band(). The page data from board.py gives the Util count (data.util), the
// percent bands (data.bands) and the ideal games (data.ideal) from core/lineup.py.
// tests/draft/test_team_builder.py shows that the engine gives the same results as core/lineup.py and core/home.py.
//
// The file has no DOM code. board.py inlines core/starts.js and then this file in the page as a plain script.
// Node loads it with require(), and it loads core/starts.js itself. The page gets the globals scoreCore, fit,
// slotRoster, footerWeeks, band and TeamBuilder.

const TeamBuilder = (() => {
  const S = typeof Starts !== "undefined" ? Starts : require("../core/starts.js");

  // The band level of a ratio: "good", "warn" or "bad", from data.bands (lineup.BANDS in core/lineup.py).
  function band(ratio, data) {
    const b = data.bands.find(([low]) => ratio >= low);
    return (b || data.bands[data.bands.length - 1])[1];
  }

  // The footer numbers of each week (Fit.team_week in core/home.py), with the result of scoreCore(core, data):
  // [{started, lost, lost_by, holes, games, ideal, days}] in the order of data.weeks.
  // games: the games of the core, with no rest nights. ideal: data.ideal (lineup.ideal_games() in core/lineup.py).
  function footerWeeks(core, result, data) {
    return data.weeks.map(w => {
      let games = 0, days = 0;
      for (const day of data.days) {
        if (day.week !== w) continue;
        days += 1;
        const b2b = day.b2b || [];
        games += core.filter(p => day.teams.includes(p.team) && !(p.rests_b2b && b2b.includes(p.team))).length;
      }
      return { ...result.weeks[w], games, ideal: data.ideal[w][core.length], days };
    });
  }

  return { scoreCore: S.scoreCore, fit: S.fit, slotRoster: S.slotRoster, footerWeeks, band };
})();

const { scoreCore, fit, slotRoster, footerWeeks, band } = TeamBuilder;

if (typeof module !== "undefined") module.exports = TeamBuilder;
