import type { ChangeEventHandler } from "react";

type UploadLandingProps = {
  onFileSelection: ChangeEventHandler<HTMLInputElement>;
};

export default function UploadLanding({
  onFileSelection,
}: UploadLandingProps) {
  return (
    <section
      className="upload-landing"
      aria-labelledby="upload-landing-heading"
    >
      <div className="upload-landing-copy">
        <p className="eyebrow">A calmer way through forms</p>
        <h1 id="upload-landing-heading">
          Bring the form. We’ll fill it out together.
        </h1>
        <p className="upload-landing-intro">
          Formless stays beside you, asks one question at a time, and helps
          make confusing wording easier to understand.
        </p>
        <div className="upload-landing-actions">
          <label className="file-button">
            Choose a fillable PDF
            <input
              className="file-input"
              id="pdf-upload"
              type="file"
              accept="application/pdf,.pdf"
              onChange={onFileSelection}
            />
          </label>
          <span>AcroForm PDF · Your original is never overwritten</span>
        </div>
        <ul className="upload-assurances" aria-label="How Formless works">
          <li>
            <span aria-hidden="true">1</span>
            <div>
              <strong>Talk naturally</strong>
              <small>Speak or type, and ask when a question is unclear.</small>
            </div>
          </li>
          <li>
            <span aria-hidden="true">2</span>
            <div>
              <strong>Check every answer</strong>
              <small>
                Nothing reaches the PDF until you explicitly confirm it.
              </small>
            </div>
          </li>
          <li>
            <span aria-hidden="true">3</span>
            <div>
              <strong>Keep the form in sight</strong>
              <small>
                Watch the completed copy update beside the conversation.
              </small>
            </div>
          </li>
        </ul>
      </div>
      <div className="upload-landing-visual" aria-hidden="true">
        <div className="landing-document">
          <span className="landing-document-heading" />
          <span />
          <span />
          <span className="landing-document-field" />
          <span />
          <span className="landing-document-field short" />
        </div>
        <div className="landing-conversation-card">
          <span className="landing-voice-orb" />
          <div>
            <small>Formless</small>
            <strong>Let’s take this one question at a time.</strong>
          </div>
        </div>
      </div>
    </section>
  );
}
