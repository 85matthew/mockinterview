import asyncio
import os
import datetime # Added for transcript saving
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import Content, Part, LiveConnectConfig, Modality
import google.generativeai.types.generation_types as genai_types # For specific exceptions

load_dotenv()

MODEL_ID = "gemini-2.0-flash-live-preview-04-09"

# Main script for the Live Interview Simulator

INTERVIEW_QUESTIONS = [
    "Tell me about yourself.",
    "Why are you interested in this role?",
    "Describe a challenging project you worked on and how you overcame it.",
    "Where do you see yourself in 5 years?",
    "Do you have any questions for me?"
]

async def run_interview_session(questions):
    print("Starting interview session...")
    transcript = []

    try:
        client = genai.Client() 
    except Exception as e:
        print(f"Error initializing Generative AI Client: {e}")
        print("Please ensure your environment is set up correctly for Vertex AI (GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI=True) and you have authenticated via `gcloud auth application-default login`.")
        transcript.append({"speaker": "System", "message": f"Error initializing Generative AI Client: {e}", "type": "error"})
        return transcript 

    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        input_audio_transcription={}, 
        output_audio_transcription={} 
    )

    print(f"Connecting to model: {MODEL_ID} with config: {config}")

    try: # Outer try for KeyboardInterrupt and general session errors
        async with client.aio.live.connect(
            model=MODEL_ID,
            config=config,
        ) as session:
            print("Session connected successfully.")
            
            try:
                system_prompt = (
                    "You are an AI practice job interviewer. I will guide the interview by indicating when it's time for specific questions. "
                    "When the candidate provides an answer to a question, your role is to give a brief, natural acknowledgment or a concise follow-up comment. "
                    "Avoid lengthy responses. After your comment, the interview will proceed to the next question or phase. "
                    "If the candidate asks you a question (especially towards the end), please answer it directly and concisely. "
                    "Let's begin the practice interview."
                )
                print(f"System: {system_prompt}")
                await session.send_client_content(
                    turns=Content(role="user", parts=[Part(text=system_prompt)])
                )
                
                # Receive ACK for system prompt
                ack_received = False
                async for message in session.receive():
                    if message.server_content and message.server_content.model_turn and message.server_content.model_turn.parts:
                        for part in message.server_content.model_turn.parts:
                            if part.text:
                                print(f"LLM (Setup ACK): {part.text}")
                                transcript.append({"speaker": "LLM", "message": part.text, "type": "setup_ack"})
                                ack_received = True
                        if message.server_content.turn_complete:
                            break 
                    elif message.server_content and message.server_content.turn_complete: # Handle case where turn completes without model_turn parts
                        break 
                if not ack_received:
                    print("No acknowledgment received from LLM for system prompt.")
                    transcript.append({"speaker": "System", "message": "No ACK from LLM for system prompt.", "type": "error"})
                    # Decide if we should proceed or not, for now, we proceed.

            except Exception as e:
                print(f"Error during session setup (system prompt send/receive): {e}")
                transcript.append({"speaker": "System", "message": f"Error during session setup: {e}", "type": "error"})
                return transcript # Exit if setup fails critically

            for i, question_to_ask in enumerate(questions):
                print(f"\n--- Question {i+1} ---")
                
                print(f"Interviewer (LLM based on script): {question_to_ask}")
                transcript.append({"speaker": "Interviewer (Script)", "message": question_to_ask, "type": "question_posed"})

                if "questions for me?" in question_to_ask.lower(): # Check if it's the candidate's turn to ask
                    llm_instruction_for_candidate_questions = "The candidate may now ask you questions. Please answer them directly and concisely."
                    print(f"System instruction to LLM: {llm_instruction_for_candidate_questions}")
                    transcript.append({"speaker": "System", "message": llm_instruction_for_candidate_questions, "type": "system_instruction_for_candidate_qs"})
                    await session.send_client_content(
                        turns=Content(role="user", parts=[Part(text=llm_instruction_for_candidate_questions)])
                    )
                    
                    # Optionally, receive and log LLM's ACK to this instruction
                    ack_candidate_q_instruction = False
                    async for message in session.receive():
                        if message.server_content and message.server_content.model_turn and message.server_content.model_turn.parts:
                            for part_ack in message.server_content.model_turn.parts:
                                if part_ack.text:
                                    print(f"LLM (ACK to candidate_q instruction): {part_ack.text}")
                                    transcript.append({"speaker": "LLM", "message": part_ack.text, "type": "ack_candidate_q_instruction"})
                                    ack_candidate_q_instruction = True
                        if message.server_content and message.server_content.turn_complete:
                            break
                    if not ack_candidate_q_instruction:
                        print("LLM did not explicitly acknowledge the instruction for candidate questions.")
                        transcript.append({"speaker": "System", "message": "LLM no ACK for candidate_q instruction", "type": "system_info"})


                try:
                    candidate_response = input("Your answer (or type 'quit' to exit): ")
                    if candidate_response.lower() == 'quit':
                        print("Exiting interview as per user request.")
                        transcript.append({"speaker": "System", "message": "User quit interview.", "type": "user_quit"})
                        break # Exit the loop of questions

                    transcript.append({"speaker": "Candidate", "message": candidate_response, "type": "candidate_answer"})

                    print(f"Sending to API (Candidate's answer): {candidate_response}")
                    await session.send_client_content(
                        turns=Content(role="user", parts=[Part(text=candidate_response)])
                    )

                    llm_response_parts = []
                    print("LLM is thinking...")
                    full_llm_response_accumulated = ""
                    output_transcription_text = ""
                    
                    async for message in session.receive():
                        if message.server_content and message.server_content.model_turn and message.server_content.model_turn.parts:
                            for part in message.server_content.model_turn.parts:
                                if part.text:
                                    print(f"LLM Response part: {part.text}")
                                    llm_response_parts.append(part.text)
                        
                        input_transcription = message.server_content.input_transcription if message.server_content else None
                        output_transcription = message.server_content.output_transcription if message.server_content else None

                        if input_transcription and input_transcription.text:
                            print(f"[Input Transcription: {input_transcription.text}]")
                        
                        if output_transcription and output_transcription.text:
                            print(f"[Output Transcription: {output_transcription.text}]")
                            output_transcription_text = output_transcription.text 
                        
                        if message.server_content and message.server_content.turn_complete:
                            full_llm_response_accumulated = "".join(llm_response_parts)
                            if full_llm_response_accumulated:
                                print(f"LLM (Full Response): {full_llm_response_accumulated}")
                                transcript.append({"speaker": "LLM", "message": full_llm_response_accumulated, "type": "llm_response_to_answer"})
                            elif output_transcription_text: 
                                print(f"LLM (Full Response from Output Transcription): {output_transcription_text}")
                                transcript.append({"speaker": "LLM", "message": output_transcription_text, "type": "llm_response_to_answer_transcribed"})
                            else:
                                print("LLM did not provide a text response for this turn.")
                                transcript.append({"speaker": "LLM", "message": "[No text response]", "type": "llm_no_text_response"})
                            break 
                    
                    if not full_llm_response_accumulated and not output_transcription_text:
                        print("No response or transcription from LLM for the candidate's answer.")
                        transcript.append({"speaker": "LLM", "message": "[No response/transcription received]", "type": "llm_failed_response"})

                except (genai_types.BlockedPromptException, genai_types.StopCandidateException) as specific_api_error:
                    print(f"API Error during question {i+1} ('{question_to_ask}'): {specific_api_error}")
                    transcript.append({"speaker": "System", "message": f"API Error for question '{question_to_ask}': {specific_api_error}", "type": "error_api"})
                    # Continue to the next question
                except Exception as e:
                    print(f"An unexpected error occurred during question {i+1} ('{question_to_ask}'): {e}")
                    transcript.append({"speaker": "System", "message": f"Unexpected error for question '{question_to_ask}': {e}", "type": "error_unexpected_question"})
                    break # For other unexpected errors during a question, stop the interview

            # Check if the loop was exited by 'quit' or completed normally
            if not any(entry['type'] == 'user_quit' for entry in transcript):
                closing_message = "Thank you for your time. This concludes the practice interview."
                print(f"\nSystem: {closing_message}")
                transcript.append({"speaker": "System", "message": closing_message, "type": "session_end"})

    except KeyboardInterrupt:
        print("\nInterview interrupted by user (Ctrl+C). Saving transcript so far.")
        transcript.append({"speaker": "System", "message": "Interview interrupted by user (Ctrl+C).", "type": "user_interrupt"})
    except genai.types.RpcError as e: # More specific error for connection issues
        print(f"A gRPC error occurred with the session: {e}")
        transcript.append({"speaker": "System", "message": f"gRPC session error: {e}", "type": "error_grpc_session"})
    except Exception as e: # Catch-all for other session-level errors
        print(f"A critical error occurred with the session: {e}")
        transcript.append({"speaker": "System", "message": f"Critical session error: {e}", "type": "error_critical_session"})
    finally:
        # The 'async with' statement handles session closing automatically.
        # If not all questions were asked (e.g. due to quit or interrupt), reflect this.
        if not any(entry['type'] == 'session_end' or entry['type'] == 'user_quit' for entry in transcript):
             transcript.append({"speaker": "System", "message": "Interview ended prematurely.", "type": "session_incomplete"})
        print("Session processing complete. Transcript will be returned.")
    
    return transcript

def save_transcript_to_file(transcript_data):
    if not transcript_data:
        print("No transcript data to save.")
        return

    now = datetime.datetime.now()
    filename = f"interview_transcript_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(filename, "w") as f:
            f.write("--- Interview Transcript ---\n\n")
            for entry in transcript_data:
                f.write(f"Speaker: {entry.get('speaker', 'Unknown')}\n")
                f.write(f"Type: {entry.get('type', 'Unknown')}\n")
                f.write(f"Message: {entry.get('message', '')}\n")
                f.write("-" * 20 + "\n")
        print(f"Transcript saved to {filename}")
    except IOError as e:
        print(f"Error saving transcript to file: {e}")

if __name__ == "__main__":
    print("Interview Questions Loaded:")
    for i, question in enumerate(INTERVIEW_QUESTIONS):
        print(f"{i+1}. {question}")
    
    print("\nStarting the interview process...")
    final_transcript = asyncio.run(run_interview_session(INTERVIEW_QUESTIONS))
    
    print("\n--- Full Interview Transcript ---")
    if final_transcript:
        for entry in final_transcript:
            print(f"{entry['speaker']} ({entry['type']}): {entry['message']}")
        save_transcript_to_file(final_transcript) # Call to save transcript
    else:
        print("No transcript was generated.")
    print("Interview process finished.")
