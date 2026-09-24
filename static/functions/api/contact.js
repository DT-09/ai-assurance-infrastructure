export async function onRequestPost({ request }) {
  try {
    const body = await request.json();

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
        return Response.json(
          { error: `${key} is required` },
          { status: 400 }
        );
      }
    }

    const email = String(body.email || "").trim();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return Response.json(
        { error: "Enter a valid work email" },
        { status: 400 }
      );
    }

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
      .map(([label, value]) => `${label}: ${String(value || "").trim()}`)
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

    return Response.json({
      status: "accepted",
      next_action: "send_email",
      mailto:
        `mailto:dhairytopia@gmail.com?subject=${subject}&body=${text}`
    });

  } catch (error) {
    return Response.json(
      { error: "Contact request could not be processed" },
      { status: 422 }
    );
  }
}