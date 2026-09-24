const corsHeaders = () => ({
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-API-Key"
});

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8"
    }
  });

async function api(request, url) {

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  /*
   * Health
   */
  if (url.pathname === "/api/health" && request.method === "GET") {
    return json({
      status: "ok",
      version: "8.0.0",
      environment: "production",
      protocol_version: "1.0"
    });
  }

  /*
   * Contact / Enterprise Assurance Intake
   */
  if (url.pathname === "/api/contact" && request.method === "POST") {

    try {

      const body = await request.json();

      /*
       * Required qualification fields.
       */
      const required = [
        "name",
        "email",
        "company",
        "system",
        "stage",
        "use_case",
        "assurance_concern",
        "production_problem"
      ];

      for (const key of required) {
        if (!String(body?.[key] || "").trim()) {
          return json(
            { error: `${key} is required` },
            400
          );
        }
      }

      /*
       * Basic email validation.
       */
      const email = String(body.email || "").trim();

      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        return json(
          { error: "Enter a valid work email" },
          400
        );
      }

      /*
       * Build the complete enterprise inquiry.
       *
       * No third-party email service is assumed.
       * The API validates the inquiry and returns a
       * mailto handoff for the visitor's own email client.
       */
      const fields = [
        ["Name", body.name],
        ["Work email", body.email],
        ["Company", body.company],
        ["Role", body.role],
        ["Company website", body.website],

        ["AI system / agent", body.system],
        ["Deployment stage", body.stage],
        ["Use case", body.use_case],
        ["Model / provider", body.model],
        ["Tools / APIs", body.tools],
        ["Autonomous actions", body.autonomous_actions],

        ["Primary assurance concern", body.assurance_concern],
        ["Production problem", body.production_problem],

        ["Desired timeline", body.timeline],
        ["Technical contact", body.technical_contact],

        ["Additional context", body.message]
      ];

      const emailBody = fields
        .map(([label, value]) => {
          return `${label}: ${String(value || "").trim()}`;
        })
        .join("\n\n");

      const subject = encodeURIComponent(
        `AAI $10K assurance engagement — ${body.company}`
      );

      const text = encodeURIComponent(
        `AAI PRODUCTION ASSURANCE ENGAGEMENT\n\n` +
        `${emailBody}\n\n` +
        `COMMERCIAL ENTRY POINT\n` +
        `$10,000 Initial Assurance Engagement\n\n` +
        `SCOPE\n` +
        `One consequential production AI workflow\n\n` +
        `Submitted through AI Assurance Infrastructure.`
      );

      return json({
        status: "accepted",
        next_action: "send_email",
        mailto:
          `mailto:dhairytopia@gmail.com?subject=${subject}&body=${text}`
      });

    } catch (error) {

      return json(
        { error: "Contact request could not be processed" },
        422
      );

    }
  }

  return null;
}

export default {

  async fetch(request, env) {

    const url = new URL(request.url);

    const response = await api(request, url);

    if (response) {

      const headers = new Headers(response.headers);

      Object.entries(corsHeaders()).forEach(([key, value]) => {
        headers.set(key, value);
      });

      return new Response(
        response.body,
        {
          status: response.status,
          headers
        }
      );
    }

    return env.ASSETS.fetch(request);
  }

};