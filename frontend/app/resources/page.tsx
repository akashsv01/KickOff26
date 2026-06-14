import { SiteFooter } from "@/components/SiteFooter";

type Resource = {

  title: string;

  host: string;

  desc: string;

  href: string;

};



type Section = {

  title: string;

  items: Resource[];

};



const SECTIONS: Section[] = [

  {

    title: "Official",

    items: [

      {

        title: "FIFA World Cup 2026",

        host: "FIFA.COM",

        desc: "The official tournament site for Canada, Mexico and the USA: news, schedule, host cities, and teams.",

        href: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",

      },

      {

        title: "Match Schedule",

        host: "FIFA.COM",

        desc: "The official kickoff times, venues, and group draw for all 104 matches.",

        href: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures",

      },

      {

        title: "Host Cities",

        host: "FIFA.COM",

        desc: "Guides to the 16 host cities across three nations, including stadiums and fan festivals.",

        href: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/host-cities",

      },

    ],

  },

  {

    title: "Watch",

    items: [

      {

        title: "FOX Sports (USA, English)",

        host: "foxsports.com",

        desc: "English-language World Cup coverage in the United States on FOX and FS1.",

        href: "https://www.foxsports.com/soccer/fifa-world-cup",

      },

      {

        title: "Telemundo Deportes (USA, Spanish)",

        host: "telemundodeportes.com",

        desc: "Spanish-language World Cup coverage in the United States on Telemundo and Universo.",

        href: "https://www.telemundodeportes.com/",

      },

      {

        title: "Find your local broadcaster",

        host: "fifa.com",

        desc: "Broadcast rights vary by country. Check the official tournament site's broadcaster list to find the rightsholder where you live.",

        href: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",

      },

    ],

  },

  {

    title: "Tickets & Travel",

    items: [

      {

        title: "Official Ticketing",

        host: "fifa.com",

        desc: "The only official place to buy World Cup 2026 tickets. Avoid unofficial resellers.",

        href: "https://www.fifa.com/en/tickets",

      },

      {

        title: "Travel Planner",

        host: "kickoff26",

        desc: "Use the in-app Travel Planner to optimize a city-hopping itinerary and export it to PDF.",

        href: "/fanplan",

      },

    ],

  },

  {

    title: "Data sources",

    items: [

      {

        title: "World Cup 2026 API (rezarahiminia)",

        host: "github.com",

        desc: "The live teams, groups, games, and score data feed powering this app's api mode.",

        href: "https://github.com/rezarahiminia/worldcup2026",

      },

      {

        title: "worldcup26.ir",

        host: "worldcup26.ir",

        desc: "Hosted endpoint for the rezarahiminia World Cup 2026 API.",

        href: "https://worldcup26.ir",

      },

      {

        title: "openfootball / worldcup.json",

        host: "github.com",

        desc: "Open-data tournament schedule and 2026 group draw used to seed fixtures, kickoff times, and venues.",

        href: "https://github.com/openfootball/worldcup.json",

      },

      {

        title: "Zafronix API",

        host: "api.zafronix.com",

        desc: "Team squads, rosters, and player data used in the Teams & Stats feature.",

        href: "https://api.zafronix.com",

      },

      {

        title: "Bolavip - 2026 World Cup coaches",

        host: "bolavip.com",

        desc: "Head-coach data for all 48 teams shown in Teams & Stats.",

        href: "https://bolavip.com/en/world-cup/2026-world-cup-coaches-all-48-managers-of-the-qualified-national-teams",

      },

      {

        title: "flag-icons",

        host: "github.com",

        desc: "MIT-licensed country flag assets used throughout the app.",

        href: "https://github.com/lipis/flag-icons",

      },

    ],

  },

];



function isExternal(href: string) {

  return href.startsWith("http");

}



export default function ResourcesPage() {

  return (

    <div className="mx-auto max-w-7xl px-4 py-8">

      <header className="resources-header">

        <div>

          <h1 className="md-page-title">Resources</h1>

          <p className="resources-sub">

            Official links and the real data sources behind KickOff26. Outbound links open in a new

            tab.

          </p>

        </div>

      </header>



      {SECTIONS.map((section) => (

        <section key={section.title}>

          <h2 className="resource-section-title">{section.title}</h2>

          <div className="resources-grid">

            {section.items.map((item) => {

              const external = isExternal(item.href);

              return (

                <a

                  key={item.title}

                  href={item.href}

                  className="resource-card"

                  {...(external

                    ? { target: "_blank", rel: "noopener noreferrer" }

                    : {})}

                >

                  <span className="resource-card-host">{item.host}</span>

                  <span className="resource-card-title">

                    {item.title}

                    {external && (

                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>

                        <path d="M7 17L17 7M17 7H8M17 7v9" />

                      </svg>

                    )}

                  </span>

                  <span className="resource-card-desc">{item.desc}</span>

                </a>

              );

            })}

          </div>

        </section>

      ))}



      <p className="resource-disclaimer">

        Ticket-price ranges shown in the Travel Planner are estimates based on published 2026

        pricing reporting and are not official quotes. Always confirm prices and availability

        through the official 2026 ticketing channel.

      </p>

      <SiteFooter />

    </div>

  );

}


