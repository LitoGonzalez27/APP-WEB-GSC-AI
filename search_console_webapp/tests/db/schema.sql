--
-- PostgreSQL database dump
--

\restrict LVe2enD77mkgaAEuQY1eDHPFNJJRUPRnrbbLtmavCSrCwFdzBGybqPibbsNcFeF

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_audit_log (
    id integer NOT NULL,
    admin_user_id integer,
    action text NOT NULL,
    target_user_id integer,
    details jsonb,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: admin_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_audit_log_id_seq OWNED BY public.admin_audit_log.id;


--
-- Name: agent_scanner_access; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_scanner_access (
    email text NOT NULL,
    added_by text,
    added_at timestamp with time zone DEFAULT now()
);


--
-- Name: agent_scanner_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_scanner_reports (
    id text NOT NULL,
    user_email text,
    client_host text,
    competitors text,
    typology text,
    score real,
    score_fiable boolean,
    agents_estado text,
    data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: ai_brand_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_brand_links (
    id integer NOT NULL,
    user_id integer,
    brand_name character varying(255) NOT NULL,
    brand_domain character varying(255) NOT NULL,
    manual_ai_project_id integer,
    ai_mode_project_id integer,
    llm_project_id integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    score_weights jsonb,
    CONSTRAINT ai_brand_links_brand_domain_check CHECK ((char_length((brand_domain)::text) >= 3)),
    CONSTRAINT ai_brand_links_brand_name_check CHECK ((char_length((brand_name)::text) >= 1))
);


--
-- Name: ai_brand_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_brand_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_brand_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_brand_links_id_seq OWNED BY public.ai_brand_links.id;


--
-- Name: ai_brand_score_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_brand_score_snapshots (
    id integer NOT NULL,
    brand_id integer,
    snapshot_date date NOT NULL,
    score numeric(5,1) NOT NULL,
    aio_visibility numeric(5,1),
    ai_mode_visibility numeric(5,1),
    llm_visibility numeric(5,1),
    channels_used text[],
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT ai_brand_score_snapshots_score_check CHECK (((score >= (0)::numeric) AND (score <= (100)::numeric)))
);


--
-- Name: ai_brand_score_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_brand_score_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_brand_score_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_brand_score_snapshots_id_seq OWNED BY public.ai_brand_score_snapshots.id;


--
-- Name: ai_mode_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_mode_events (
    id integer NOT NULL,
    project_id integer,
    event_date date NOT NULL,
    event_type character varying(50) NOT NULL,
    event_title character varying(255) NOT NULL,
    event_description text,
    keywords_affected integer DEFAULT 0,
    user_id integer,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT ai_mode_events_event_title_check CHECK ((char_length((event_title)::text) >= 1))
);


--
-- Name: ai_mode_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_mode_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_mode_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_mode_events_id_seq OWNED BY public.ai_mode_events.id;


--
-- Name: ai_mode_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_mode_keywords (
    id integer NOT NULL,
    project_id integer,
    keyword character varying(500) NOT NULL,
    is_active boolean DEFAULT true,
    added_at timestamp without time zone DEFAULT now(),
    CONSTRAINT ai_mode_keywords_keyword_check CHECK ((char_length((keyword)::text) >= 1))
);


--
-- Name: ai_mode_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_mode_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_mode_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_mode_keywords_id_seq OWNED BY public.ai_mode_keywords.id;


--
-- Name: ai_mode_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_mode_projects (
    id integer NOT NULL,
    user_id integer,
    name character varying(255) NOT NULL,
    description text,
    brand_name character varying(255) NOT NULL,
    country_code character varying(3) DEFAULT 'US'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    selected_competitors jsonb DEFAULT '[]'::jsonb,
    topic_clusters jsonb,
    is_paused_by_quota boolean DEFAULT false,
    paused_until timestamp with time zone,
    paused_at timestamp with time zone,
    paused_reason text,
    analysis_frequency_days integer DEFAULT 1,
    monthly_ru_limit integer,
    CONSTRAINT ai_mode_projects_brand_name_check CHECK ((char_length((brand_name)::text) >= 2)),
    CONSTRAINT ai_mode_projects_name_check CHECK ((char_length((name)::text) >= 1))
);


--
-- Name: ai_mode_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_mode_projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_mode_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_mode_projects_id_seq OWNED BY public.ai_mode_projects.id;


--
-- Name: ai_mode_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_mode_results (
    id integer NOT NULL,
    project_id integer,
    keyword_id integer,
    analysis_date date NOT NULL,
    keyword character varying(500) NOT NULL,
    brand_name character varying(255) NOT NULL,
    brand_mentioned boolean DEFAULT false,
    mention_position integer,
    mention_context text,
    total_sources integer DEFAULT 0,
    sentiment character varying(50),
    raw_ai_mode_data jsonb,
    country_code character varying(3) DEFAULT 'US'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT ai_mode_results_total_sources_check CHECK ((total_sources >= 0))
);


--
-- Name: ai_mode_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_mode_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_mode_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_mode_results_id_seq OWNED BY public.ai_mode_results.id;


--
-- Name: ai_mode_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_mode_snapshots (
    id integer NOT NULL,
    project_id integer,
    snapshot_date date NOT NULL,
    total_keywords integer NOT NULL,
    active_keywords integer NOT NULL,
    total_mentions integer DEFAULT 0,
    avg_position numeric(5,2),
    visibility_percentage numeric(5,2),
    change_type character varying(50),
    change_description text,
    keywords_added integer DEFAULT 0,
    keywords_removed integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT ai_mode_snapshots_total_keywords_check CHECK ((total_keywords >= 0))
);


--
-- Name: ai_mode_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_mode_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_mode_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_mode_snapshots_id_seq OWNED BY public.ai_mode_snapshots.id;


--
-- Name: ai_overview_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_overview_analysis (
    id integer NOT NULL,
    site_url character varying(255) NOT NULL,
    keyword character varying(255) NOT NULL,
    analysis_date timestamp without time zone DEFAULT now(),
    has_ai_overview boolean DEFAULT false,
    domain_is_ai_source boolean DEFAULT false,
    impact_score integer DEFAULT 0,
    country_code character varying(3),
    keyword_word_count integer,
    clicks_m1 integer DEFAULT 0,
    clicks_m2 integer DEFAULT 0,
    delta_clicks_absolute integer DEFAULT 0,
    delta_clicks_percent numeric(10,2),
    impressions_m1 integer DEFAULT 0,
    impressions_m2 integer DEFAULT 0,
    ctr_m1 numeric(5,2),
    ctr_m2 numeric(5,2),
    position_m1 numeric(5,2),
    position_m2 numeric(5,2),
    ai_elements_count integer DEFAULT 0,
    domain_ai_source_position integer,
    raw_data jsonb,
    user_id integer,
    created_at timestamp without time zone DEFAULT now(),
    aio_serp_position character varying(10)
);


--
-- Name: ai_overview_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_overview_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_overview_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_overview_analysis_id_seq OWNED BY public.ai_overview_analysis.id;


--
-- Name: gsc_properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gsc_properties (
    id integer NOT NULL,
    user_id integer,
    connection_id integer,
    site_url text NOT NULL,
    permission_level text,
    verified boolean,
    last_seen timestamp without time zone DEFAULT now(),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: gsc_properties_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gsc_properties_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gsc_properties_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gsc_properties_id_seq OWNED BY public.gsc_properties.id;


--
-- Name: llm_model_changelog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_model_changelog (
    id integer NOT NULL,
    llm_provider character varying(50) NOT NULL,
    old_model_id character varying(100),
    new_model_id character varying(100) NOT NULL,
    old_display_name character varying(255),
    new_display_name character varying(255),
    change_type character varying(30) NOT NULL,
    changed_by character varying(100),
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: llm_model_changelog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_model_changelog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_model_changelog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_model_changelog_id_seq OWNED BY public.llm_model_changelog.id;


--
-- Name: llm_model_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_model_registry (
    id integer NOT NULL,
    llm_provider character varying(50) NOT NULL,
    model_id character varying(100) NOT NULL,
    model_display_name character varying(255),
    cost_per_1m_input_tokens numeric(10,4),
    cost_per_1m_output_tokens numeric(10,4),
    max_tokens integer,
    max_output_tokens integer,
    supports_vision boolean DEFAULT false,
    supports_functions boolean DEFAULT false,
    is_current boolean DEFAULT false,
    is_available boolean DEFAULT true,
    detected_at timestamp without time zone DEFAULT now(),
    last_used_at timestamp without time zone,
    total_queries integer DEFAULT 0,
    total_tokens_consumed bigint DEFAULT 0,
    total_cost numeric(12,4) DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    model_category character varying(30) DEFAULT 'chat'::character varying,
    knowledge_cutoff character varying(50),
    knowledge_cutoff_date date,
    pending_approval boolean DEFAULT false,
    approval_token character varying(128),
    approval_token_expires_at timestamp without time zone,
    pre_switch_validated boolean DEFAULT false,
    cost_per_1k_search_calls numeric(10,4)
);


--
-- Name: llm_model_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_model_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_model_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_model_registry_id_seq OWNED BY public.llm_model_registry.id;


--
-- Name: llm_models; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_models (
    id integer NOT NULL,
    llm_provider character varying(50) NOT NULL,
    model_id character varying(100) NOT NULL,
    model_name character varying(200) NOT NULL,
    cost_per_1m_input_tokens numeric(10,2) NOT NULL,
    cost_per_1m_output_tokens numeric(10,2) NOT NULL,
    max_tokens integer,
    is_current boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: llm_models_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_models_id_seq OWNED BY public.llm_models.id;


--
-- Name: llm_monitoring_analysis_lock; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_analysis_lock (
    id integer DEFAULT 1 NOT NULL,
    is_running boolean DEFAULT false,
    started_at timestamp without time zone,
    started_by text,
    CONSTRAINT single_row CHECK ((id = 1))
);


--
-- Name: llm_monitoring_analysis_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_analysis_runs (
    id integer NOT NULL,
    started_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    status text DEFAULT 'running'::text,
    total_projects integer DEFAULT 0,
    successful_projects integer DEFAULT 0,
    failed_projects integer DEFAULT 0,
    total_queries integer DEFAULT 0,
    error_message text,
    triggered_by text DEFAULT 'cron'::text,
    project_results jsonb
);


--
-- Name: llm_monitoring_analysis_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_analysis_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_analysis_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_analysis_runs_id_seq OWNED BY public.llm_monitoring_analysis_runs.id;


--
-- Name: llm_monitoring_fanout_queries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_fanout_queries (
    id bigint NOT NULL,
    result_id integer NOT NULL,
    project_id integer NOT NULL,
    query_id integer NOT NULL,
    llm_provider character varying(50) NOT NULL,
    analysis_date date NOT NULL,
    round smallint NOT NULL,
    "position" smallint NOT NULL,
    action character varying(16) NOT NULL,
    query_text text,
    query_normalized text,
    query_cluster_id integer,
    url text,
    url_host text,
    sources jsonb DEFAULT '[]'::jsonb NOT NULL,
    brand_in_sources boolean,
    competitor_hosts text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_monitoring_fanout_queries_action_check CHECK (((action)::text = ANY ((ARRAY['search'::character varying, 'open_page'::character varying, 'find_in_page'::character varying, 'fetch_url'::character varying])::text[])))
);


--
-- Name: llm_monitoring_fanout_queries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_fanout_queries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_fanout_queries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_fanout_queries_id_seq OWNED BY public.llm_monitoring_fanout_queries.id;


--
-- Name: llm_monitoring_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_projects (
    id integer NOT NULL,
    user_id integer,
    name character varying(255) NOT NULL,
    brand_name character varying(255) NOT NULL,
    industry character varying(255) NOT NULL,
    enabled_llms text[] DEFAULT ARRAY['openai'::text, 'anthropic'::text, 'google'::text, 'perplexity'::text],
    competitors jsonb DEFAULT '[]'::jsonb,
    language character varying(10) DEFAULT 'es'::character varying,
    queries_per_llm integer DEFAULT 15,
    is_active boolean DEFAULT true,
    last_analysis_date timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    brand_domain character varying(255),
    brand_keywords jsonb DEFAULT '[]'::jsonb,
    competitor_domains jsonb DEFAULT '[]'::jsonb,
    competitor_keywords jsonb DEFAULT '[]'::jsonb,
    country_code character varying(2) DEFAULT 'ES'::character varying,
    selected_competitors jsonb DEFAULT '[]'::jsonb,
    is_paused_by_quota boolean DEFAULT false,
    paused_until timestamp with time zone,
    paused_at timestamp with time zone,
    paused_reason text,
    prompt_clusters jsonb DEFAULT '{"enabled": false, "clusters": []}'::jsonb,
    prompt_sets jsonb DEFAULT '{"sets": [], "enabled": false}'::jsonb,
    monthly_units_limit integer,
    analysis_frequency_days integer DEFAULT 1,
    search_mode character varying(10) DEFAULT 'off'::character varying NOT NULL,
    search_enabled_at timestamp with time zone,
    CONSTRAINT llm_monitoring_projects_brand_name_check CHECK ((char_length((brand_name)::text) >= 2)),
    CONSTRAINT llm_monitoring_projects_queries_per_llm_check CHECK (((queries_per_llm >= 5) AND (queries_per_llm <= 5000))),
    CONSTRAINT llm_monitoring_projects_search_mode_check CHECK (((search_mode)::text = ANY ((ARRAY['off'::character varying, 'auto'::character varying])::text[])))
);


--
-- Name: llm_monitoring_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_projects_id_seq OWNED BY public.llm_monitoring_projects.id;


--
-- Name: llm_monitoring_queries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_queries (
    id integer NOT NULL,
    project_id integer,
    query_text text NOT NULL,
    language character varying(10) DEFAULT 'es'::character varying,
    query_type character varying(50) DEFAULT 'general'::character varying,
    is_active boolean DEFAULT true,
    added_at timestamp without time zone DEFAULT now(),
    topic_cluster text,
    prompt_set text,
    CONSTRAINT llm_monitoring_queries_query_text_check CHECK ((char_length(query_text) >= 10))
);


--
-- Name: llm_monitoring_queries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_queries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_queries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_queries_id_seq OWNED BY public.llm_monitoring_queries.id;


--
-- Name: llm_monitoring_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_results (
    id integer NOT NULL,
    project_id integer,
    query_id integer,
    analysis_date date NOT NULL,
    llm_provider character varying(50) NOT NULL,
    model_used character varying(100),
    query_text text NOT NULL,
    brand_name character varying(255) NOT NULL,
    brand_mentioned boolean DEFAULT false,
    mention_count integer DEFAULT 0,
    mention_contexts text[] DEFAULT ARRAY[]::text[],
    appears_in_numbered_list boolean DEFAULT false,
    position_in_list integer,
    total_items_in_list integer,
    sentiment character varying(50),
    sentiment_score numeric(3,2),
    competitors_mentioned jsonb DEFAULT '{}'::jsonb,
    full_response text,
    response_length integer,
    tokens_used integer,
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(10,6),
    response_time_ms integer,
    created_at timestamp without time zone DEFAULT now(),
    sources jsonb DEFAULT '[]'::jsonb,
    has_error boolean DEFAULT false,
    error_message text,
    updated_at timestamp without time zone DEFAULT now(),
    position_source character varying(10) DEFAULT NULL::character varying,
    execution_metadata jsonb,
    prompt_version character varying(20) DEFAULT NULL::character varying,
    search_queries jsonb DEFAULT '[]'::jsonb NOT NULL,
    units_consumed smallint DEFAULT 1 NOT NULL,
    CONSTRAINT llm_monitoring_results_cost_usd_check CHECK ((cost_usd >= (0)::numeric)),
    CONSTRAINT llm_monitoring_results_mention_count_check CHECK ((mention_count >= 0))
);


--
-- Name: COLUMN llm_monitoring_results.position_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_monitoring_results.position_source IS 'Origen de la posición detectada: text (mención en texto), link (solo en URL), both (texto + URL)';


--
-- Name: llm_monitoring_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_results_id_seq OWNED BY public.llm_monitoring_results.id;


--
-- Name: llm_monitoring_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_monitoring_snapshots (
    id integer NOT NULL,
    project_id integer,
    snapshot_date date NOT NULL,
    llm_provider character varying(50) NOT NULL,
    total_queries integer NOT NULL,
    total_mentions integer DEFAULT 0,
    mention_rate numeric(5,2),
    avg_position numeric(5,2),
    appeared_in_top3 integer DEFAULT 0,
    appeared_in_top5 integer DEFAULT 0,
    appeared_in_top10 integer DEFAULT 0,
    total_competitor_mentions integer DEFAULT 0,
    share_of_voice numeric(5,2),
    competitor_breakdown jsonb DEFAULT '{}'::jsonb,
    positive_mentions integer DEFAULT 0,
    neutral_mentions integer DEFAULT 0,
    negative_mentions integer DEFAULT 0,
    avg_sentiment_score numeric(3,2),
    avg_response_time_ms integer,
    total_cost_usd numeric(10,4),
    total_tokens integer,
    created_at timestamp without time zone DEFAULT now(),
    weighted_share_of_voice numeric(5,2) DEFAULT NULL::numeric,
    weighted_competitor_breakdown jsonb,
    CONSTRAINT llm_monitoring_snapshots_mention_rate_check CHECK (((mention_rate >= (0)::numeric) AND (mention_rate <= (100)::numeric))),
    CONSTRAINT llm_monitoring_snapshots_share_of_voice_check CHECK (((share_of_voice >= (0)::numeric) AND (share_of_voice <= (100)::numeric))),
    CONSTRAINT llm_monitoring_snapshots_total_queries_check CHECK ((total_queries >= 0))
);


--
-- Name: llm_monitoring_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_monitoring_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_monitoring_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_monitoring_snapshots_id_seq OWNED BY public.llm_monitoring_snapshots.id;


--
-- Name: llm_url_content_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_url_content_analysis (
    id integer NOT NULL,
    project_id integer NOT NULL,
    url text NOT NULL,
    url_hash character(64) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    http_status integer,
    page_title text,
    brand_mentioned boolean DEFAULT false NOT NULL,
    brand_mention_count integer DEFAULT 0 NOT NULL,
    brand_linked boolean DEFAULT false NOT NULL,
    brand_anchor_texts jsonb DEFAULT '[]'::jsonb NOT NULL,
    competitors_found jsonb DEFAULT '[]'::jsonb NOT NULL,
    opportunity character varying(20),
    error_reason text,
    fetched_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    fetch_method character varying(20) DEFAULT 'direct'::character varying NOT NULL
);


--
-- Name: llm_url_content_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_url_content_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_url_content_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_url_content_analysis_id_seq OWNED BY public.llm_url_content_analysis.id;


--
-- Name: llm_visibility_comparison; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.llm_visibility_comparison AS
 SELECT s.project_id,
    s.snapshot_date,
    p.brand_name,
    p.industry,
    max(
        CASE
            WHEN ((s.llm_provider)::text = 'openai'::text) THEN s.mention_rate
            ELSE NULL::numeric
        END) AS chatgpt_mention_rate,
    max(
        CASE
            WHEN ((s.llm_provider)::text = 'anthropic'::text) THEN s.mention_rate
            ELSE NULL::numeric
        END) AS claude_mention_rate,
    max(
        CASE
            WHEN ((s.llm_provider)::text = 'google'::text) THEN s.mention_rate
            ELSE NULL::numeric
        END) AS gemini_mention_rate,
    max(
        CASE
            WHEN ((s.llm_provider)::text = 'perplexity'::text) THEN s.mention_rate
            ELSE NULL::numeric
        END) AS perplexity_mention_rate,
    avg(s.mention_rate) AS avg_mention_rate_all_llms,
    avg(s.share_of_voice) AS avg_share_of_voice,
    avg(s.avg_sentiment_score) AS avg_sentiment_score,
    sum(s.total_cost_usd) AS total_cost_all_llms,
    ( SELECT s2.llm_provider
           FROM public.llm_monitoring_snapshots s2
          WHERE ((s2.project_id = s.project_id) AND (s2.snapshot_date = s.snapshot_date))
          ORDER BY s2.mention_rate DESC
         LIMIT 1) AS best_llm_for_mentions,
    ( SELECT s2.llm_provider
           FROM public.llm_monitoring_snapshots s2
          WHERE ((s2.project_id = s.project_id) AND (s2.snapshot_date = s.snapshot_date))
          ORDER BY s2.mention_rate
         LIMIT 1) AS worst_llm_for_mentions
   FROM (public.llm_monitoring_snapshots s
     JOIN public.llm_monitoring_projects p ON ((s.project_id = p.id)))
  GROUP BY s.project_id, s.snapshot_date, p.brand_name, p.industry;


--
-- Name: manual_ai_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_events (
    id integer NOT NULL,
    project_id integer,
    event_date date NOT NULL,
    event_type character varying(50) NOT NULL,
    event_title character varying(255) NOT NULL,
    event_description text,
    keywords_affected integer DEFAULT 0,
    user_id integer,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT manual_ai_events_event_title_check CHECK ((char_length((event_title)::text) >= 1))
);


--
-- Name: manual_ai_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_events_id_seq OWNED BY public.manual_ai_events.id;


--
-- Name: manual_ai_global_domains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_global_domains (
    id integer NOT NULL,
    project_id integer,
    keyword_id integer,
    analysis_date date NOT NULL,
    keyword character varying(500) NOT NULL,
    project_domain character varying(255) NOT NULL,
    detected_domain character varying(255) NOT NULL,
    domain_position integer NOT NULL,
    domain_title text,
    domain_source_url text,
    country_code character varying(3) DEFAULT 'US'::character varying,
    is_project_domain boolean DEFAULT false,
    is_selected_competitor boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT manual_ai_global_domains_detected_domain_check CHECK ((char_length((detected_domain)::text) >= 3)),
    CONSTRAINT manual_ai_global_domains_domain_position_check CHECK ((domain_position > 0))
);


--
-- Name: manual_ai_global_domains_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_global_domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_global_domains_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_global_domains_id_seq OWNED BY public.manual_ai_global_domains.id;


--
-- Name: manual_ai_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_keywords (
    id integer NOT NULL,
    project_id integer,
    keyword character varying(500) NOT NULL,
    is_active boolean DEFAULT true,
    added_at timestamp without time zone DEFAULT now(),
    CONSTRAINT manual_ai_keywords_keyword_check CHECK ((char_length((keyword)::text) >= 1))
);


--
-- Name: manual_ai_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_keywords_id_seq OWNED BY public.manual_ai_keywords.id;


--
-- Name: manual_ai_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_projects (
    id integer NOT NULL,
    user_id integer,
    name character varying(255) NOT NULL,
    description text,
    domain character varying(255) NOT NULL,
    country_code character varying(3) DEFAULT 'US'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    selected_competitors jsonb DEFAULT '[]'::jsonb,
    topic_clusters jsonb DEFAULT '{"enabled": false, "clusters": []}'::jsonb,
    is_paused_by_quota boolean DEFAULT false,
    paused_until timestamp with time zone,
    paused_at timestamp with time zone,
    paused_reason text,
    analysis_frequency_days integer DEFAULT 1,
    monthly_ru_limit integer,
    CONSTRAINT check_max_competitors CHECK ((jsonb_array_length(COALESCE(selected_competitors, '[]'::jsonb)) <= 4)),
    CONSTRAINT manual_ai_projects_domain_check CHECK ((char_length((domain)::text) >= 4)),
    CONSTRAINT manual_ai_projects_name_check CHECK ((char_length((name)::text) >= 1))
);


--
-- Name: manual_ai_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_projects_id_seq OWNED BY public.manual_ai_projects.id;


--
-- Name: manual_ai_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_results (
    id integer NOT NULL,
    project_id integer,
    keyword_id integer,
    analysis_date date NOT NULL,
    keyword character varying(500) NOT NULL,
    domain character varying(255) NOT NULL,
    has_ai_overview boolean DEFAULT false,
    domain_mentioned boolean DEFAULT false,
    domain_position integer,
    ai_elements_count integer DEFAULT 0,
    impact_score integer DEFAULT 0,
    raw_serp_data jsonb,
    ai_analysis_data jsonb,
    country_code character varying(3) DEFAULT 'US'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT manual_ai_results_ai_elements_count_check CHECK ((ai_elements_count >= 0)),
    CONSTRAINT manual_ai_results_impact_score_check CHECK ((impact_score >= 0))
);


--
-- Name: manual_ai_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_results_id_seq OWNED BY public.manual_ai_results.id;


--
-- Name: manual_ai_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_ai_snapshots (
    id integer NOT NULL,
    project_id integer,
    snapshot_date date NOT NULL,
    total_keywords integer NOT NULL,
    active_keywords integer NOT NULL,
    keywords_with_ai integer DEFAULT 0,
    domain_mentions integer DEFAULT 0,
    avg_position numeric(5,2),
    visibility_percentage numeric(5,2),
    change_type character varying(50),
    change_description text,
    keywords_added integer DEFAULT 0,
    keywords_removed integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT manual_ai_snapshots_active_keywords_check CHECK ((active_keywords >= 0)),
    CONSTRAINT manual_ai_snapshots_keywords_with_ai_check CHECK ((keywords_with_ai >= 0)),
    CONSTRAINT manual_ai_snapshots_total_keywords_check CHECK ((total_keywords >= 0))
);


--
-- Name: manual_ai_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_ai_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_ai_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_ai_snapshots_id_seq OWNED BY public.manual_ai_snapshots.id;


--
-- Name: oauth_connections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oauth_connections (
    id integer NOT NULL,
    user_id integer,
    provider text DEFAULT 'google'::text NOT NULL,
    google_account_id text,
    google_email text,
    access_token text,
    refresh_token_encrypted text,
    token_uri text,
    client_id text,
    client_secret text,
    scopes text,
    expires_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: oauth_connections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oauth_connections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oauth_connections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oauth_connections_id_seq OWNED BY public.oauth_connections.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token character varying(255) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.password_reset_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.password_reset_tokens_id_seq OWNED BY public.password_reset_tokens.id;


--
-- Name: project_collaborators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_collaborators (
    id integer NOT NULL,
    module_name character varying(32) NOT NULL,
    project_id integer NOT NULL,
    owner_user_id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying(20) DEFAULT 'viewer'::character varying NOT NULL,
    invited_by_user_id integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT project_collaborators_module_name_check CHECK (((module_name)::text = ANY ((ARRAY['llm_monitoring'::character varying, 'manual_ai'::character varying, 'ai_mode'::character varying, 'ai_summary'::character varying])::text[]))),
    CONSTRAINT project_collaborators_role_check CHECK (((role)::text = 'viewer'::text))
);


--
-- Name: project_collaborators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_collaborators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_collaborators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_collaborators_id_seq OWNED BY public.project_collaborators.id;


--
-- Name: project_invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_invitations (
    id integer NOT NULL,
    module_name character varying(32) NOT NULL,
    project_id integer NOT NULL,
    owner_user_id integer NOT NULL,
    inviter_user_id integer NOT NULL,
    invitee_email text NOT NULL,
    invitee_name text,
    role character varying(20) DEFAULT 'viewer'::character varying NOT NULL,
    token_hash text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    accepted_by_user_id integer,
    accepted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT project_invitations_module_name_check CHECK (((module_name)::text = ANY ((ARRAY['llm_monitoring'::character varying, 'manual_ai'::character varying, 'ai_mode'::character varying, 'ai_summary'::character varying])::text[]))),
    CONSTRAINT project_invitations_role_check CHECK (((role)::text = 'viewer'::text)),
    CONSTRAINT project_invitations_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'revoked'::character varying, 'expired'::character varying])::text[])))
);


--
-- Name: project_invitations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_invitations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_invitations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_invitations_id_seq OWNED BY public.project_invitations.id;


--
-- Name: quota_usage_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quota_usage_events (
    id integer NOT NULL,
    user_id integer,
    ru_consumed integer DEFAULT 1,
    source character varying(50),
    keyword character varying(255),
    country_code character varying(3),
    "timestamp" timestamp with time zone DEFAULT now(),
    metadata jsonb,
    operation_type character varying(50),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: quota_usage_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quota_usage_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quota_usage_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quota_usage_events_id_seq OWNED BY public.quota_usage_events.id;


--
-- Name: seo_ai_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seo_ai_analyses (
    id integer NOT NULL,
    user_id integer NOT NULL,
    site_url character varying(255) NOT NULL,
    country character varying(10) DEFAULT ''::character varying NOT NULL,
    date_range_start date NOT NULL,
    date_range_end date NOT NULL,
    comparison_start date,
    comparison_end date,
    model_used character varying(100) DEFAULT 'claude-sonnet-4-6'::character varying NOT NULL,
    analysis_name character varying(255) NOT NULL,
    context_snapshot jsonb NOT NULL,
    recommendations jsonb,
    status character varying(20) DEFAULT 'generating'::character varying NOT NULL,
    error_message text,
    tokens_used integer DEFAULT 0,
    cost_usd numeric(10,6) DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_seo_analysis_status CHECK (((status)::text = ANY ((ARRAY['generating'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: seo_ai_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seo_ai_analyses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seo_ai_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seo_ai_analyses_id_seq OWNED BY public.seo_ai_analyses.id;


--
-- Name: stripe_webhook_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stripe_webhook_events (
    event_id character varying(120) NOT NULL,
    event_type character varying(80) NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    status character varying(20) DEFAULT 'in_progress'::character varying NOT NULL,
    error_message text
);


--
-- Name: user_llm_api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_llm_api_keys (
    id integer NOT NULL,
    user_id integer,
    openai_api_key_encrypted text,
    anthropic_api_key_encrypted text,
    google_api_key_encrypted text,
    perplexity_api_key_encrypted text,
    monthly_budget_usd numeric(10,2) DEFAULT 100.00,
    current_month_spend numeric(10,4) DEFAULT 0,
    spending_alert_threshold numeric(5,2) DEFAULT 80.0,
    last_spend_reset timestamp without time zone DEFAULT now(),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT user_llm_api_keys_current_month_spend_check CHECK ((current_month_spend >= (0)::numeric)),
    CONSTRAINT user_llm_api_keys_monthly_budget_usd_check CHECK ((monthly_budget_usd > (0)::numeric)),
    CONSTRAINT user_llm_api_keys_spending_alert_threshold_check CHECK (((spending_alert_threshold >= (0)::numeric) AND (spending_alert_threshold <= (100)::numeric)))
);


--
-- Name: user_llm_api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_llm_api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_llm_api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_llm_api_keys_id_seq OWNED BY public.user_llm_api_keys.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    google_id text,
    email text NOT NULL,
    name text NOT NULL,
    picture text,
    password_hash text,
    role text DEFAULT 'user'::text,
    is_active boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    stripe_customer_id character varying(255),
    plan character varying(20) DEFAULT 'free'::character varying,
    billing_status character varying(20) DEFAULT 'active'::character varying,
    quota_limit integer DEFAULT 0,
    quota_used integer DEFAULT 0,
    quota_reset_date timestamp with time zone,
    subscription_id character varying(255),
    current_period_start timestamp with time zone,
    current_period_end timestamp with time zone,
    current_plan character varying(20) DEFAULT 'free'::character varying,
    pending_plan character varying(20),
    pending_plan_date timestamp with time zone,
    custom_quota_limit integer,
    custom_quota_notes text,
    custom_quota_assigned_by character varying(255) DEFAULT NULL::character varying,
    custom_quota_assigned_date timestamp without time zone,
    last_login_at timestamp without time zone,
    trial_used boolean DEFAULT false,
    ai_overview_paused_until timestamp with time zone,
    ai_overview_paused_at timestamp with time zone,
    ai_overview_paused_reason text,
    custom_llm_prompts_limit integer,
    custom_llm_monthly_units_limit integer,
    custom_manual_ai_max_projects integer,
    custom_manual_ai_keywords_limit integer,
    custom_ai_mode_max_projects integer,
    custom_ai_mode_keywords_limit integer,
    custom_llm_max_projects integer,
    CONSTRAINT chk_current_plan CHECK (((current_plan)::text = ANY ((ARRAY['free'::character varying, 'basic'::character varying, 'premium'::character varying, 'business'::character varying, 'enterprise'::character varying])::text[]))),
    CONSTRAINT chk_pending_plan CHECK (((pending_plan)::text = ANY ((ARRAY['free'::character varying, 'basic'::character varying, 'premium'::character varying, 'business'::character varying, 'enterprise'::character varying])::text[]))),
    CONSTRAINT chk_plan CHECK (((plan)::text = ANY ((ARRAY['free'::character varying, 'basic'::character varying, 'premium'::character varying, 'business'::character varying, 'enterprise'::character varying])::text[])))
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: admin_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log ALTER COLUMN id SET DEFAULT nextval('public.admin_audit_log_id_seq'::regclass);


--
-- Name: ai_brand_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links ALTER COLUMN id SET DEFAULT nextval('public.ai_brand_links_id_seq'::regclass);


--
-- Name: ai_brand_score_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_score_snapshots ALTER COLUMN id SET DEFAULT nextval('public.ai_brand_score_snapshots_id_seq'::regclass);


--
-- Name: ai_mode_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_events ALTER COLUMN id SET DEFAULT nextval('public.ai_mode_events_id_seq'::regclass);


--
-- Name: ai_mode_keywords id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_keywords ALTER COLUMN id SET DEFAULT nextval('public.ai_mode_keywords_id_seq'::regclass);


--
-- Name: ai_mode_projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_projects ALTER COLUMN id SET DEFAULT nextval('public.ai_mode_projects_id_seq'::regclass);


--
-- Name: ai_mode_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_results ALTER COLUMN id SET DEFAULT nextval('public.ai_mode_results_id_seq'::regclass);


--
-- Name: ai_mode_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_snapshots ALTER COLUMN id SET DEFAULT nextval('public.ai_mode_snapshots_id_seq'::regclass);


--
-- Name: ai_overview_analysis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_overview_analysis ALTER COLUMN id SET DEFAULT nextval('public.ai_overview_analysis_id_seq'::regclass);


--
-- Name: gsc_properties id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gsc_properties ALTER COLUMN id SET DEFAULT nextval('public.gsc_properties_id_seq'::regclass);


--
-- Name: llm_model_changelog id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model_changelog ALTER COLUMN id SET DEFAULT nextval('public.llm_model_changelog_id_seq'::regclass);


--
-- Name: llm_model_registry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model_registry ALTER COLUMN id SET DEFAULT nextval('public.llm_model_registry_id_seq'::regclass);


--
-- Name: llm_models id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models ALTER COLUMN id SET DEFAULT nextval('public.llm_models_id_seq'::regclass);


--
-- Name: llm_monitoring_analysis_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_analysis_runs ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_analysis_runs_id_seq'::regclass);


--
-- Name: llm_monitoring_fanout_queries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_fanout_queries ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_fanout_queries_id_seq'::regclass);


--
-- Name: llm_monitoring_projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_projects ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_projects_id_seq'::regclass);


--
-- Name: llm_monitoring_queries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_queries ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_queries_id_seq'::regclass);


--
-- Name: llm_monitoring_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_results ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_results_id_seq'::regclass);


--
-- Name: llm_monitoring_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_snapshots ALTER COLUMN id SET DEFAULT nextval('public.llm_monitoring_snapshots_id_seq'::regclass);


--
-- Name: llm_url_content_analysis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_url_content_analysis ALTER COLUMN id SET DEFAULT nextval('public.llm_url_content_analysis_id_seq'::regclass);


--
-- Name: manual_ai_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_events ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_events_id_seq'::regclass);


--
-- Name: manual_ai_global_domains id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_global_domains ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_global_domains_id_seq'::regclass);


--
-- Name: manual_ai_keywords id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_keywords ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_keywords_id_seq'::regclass);


--
-- Name: manual_ai_projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_projects ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_projects_id_seq'::regclass);


--
-- Name: manual_ai_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_results ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_results_id_seq'::regclass);


--
-- Name: manual_ai_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_snapshots ALTER COLUMN id SET DEFAULT nextval('public.manual_ai_snapshots_id_seq'::regclass);


--
-- Name: oauth_connections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connections ALTER COLUMN id SET DEFAULT nextval('public.oauth_connections_id_seq'::regclass);


--
-- Name: password_reset_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens ALTER COLUMN id SET DEFAULT nextval('public.password_reset_tokens_id_seq'::regclass);


--
-- Name: project_collaborators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators ALTER COLUMN id SET DEFAULT nextval('public.project_collaborators_id_seq'::regclass);


--
-- Name: project_invitations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations ALTER COLUMN id SET DEFAULT nextval('public.project_invitations_id_seq'::regclass);


--
-- Name: quota_usage_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_usage_events ALTER COLUMN id SET DEFAULT nextval('public.quota_usage_events_id_seq'::regclass);


--
-- Name: seo_ai_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seo_ai_analyses ALTER COLUMN id SET DEFAULT nextval('public.seo_ai_analyses_id_seq'::regclass);


--
-- Name: user_llm_api_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_llm_api_keys ALTER COLUMN id SET DEFAULT nextval('public.user_llm_api_keys_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: admin_audit_log admin_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_pkey PRIMARY KEY (id);


--
-- Name: agent_scanner_access agent_scanner_access_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scanner_access
    ADD CONSTRAINT agent_scanner_access_pkey PRIMARY KEY (email);


--
-- Name: agent_scanner_reports agent_scanner_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_scanner_reports
    ADD CONSTRAINT agent_scanner_reports_pkey PRIMARY KEY (id);


--
-- Name: ai_brand_links ai_brand_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_pkey PRIMARY KEY (id);


--
-- Name: ai_brand_links ai_brand_links_user_id_brand_domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_user_id_brand_domain_key UNIQUE (user_id, brand_domain);


--
-- Name: ai_brand_score_snapshots ai_brand_score_snapshots_brand_id_snapshot_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_score_snapshots
    ADD CONSTRAINT ai_brand_score_snapshots_brand_id_snapshot_date_key UNIQUE (brand_id, snapshot_date);


--
-- Name: ai_brand_score_snapshots ai_brand_score_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_score_snapshots
    ADD CONSTRAINT ai_brand_score_snapshots_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_events ai_mode_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_events
    ADD CONSTRAINT ai_mode_events_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_keywords ai_mode_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_keywords
    ADD CONSTRAINT ai_mode_keywords_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_keywords ai_mode_keywords_project_id_keyword_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_keywords
    ADD CONSTRAINT ai_mode_keywords_project_id_keyword_key UNIQUE (project_id, keyword);


--
-- Name: ai_mode_projects ai_mode_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_projects
    ADD CONSTRAINT ai_mode_projects_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_projects ai_mode_projects_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_projects
    ADD CONSTRAINT ai_mode_projects_user_id_name_key UNIQUE (user_id, name);


--
-- Name: ai_mode_results ai_mode_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_results
    ADD CONSTRAINT ai_mode_results_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_results ai_mode_results_project_id_keyword_id_analysis_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_results
    ADD CONSTRAINT ai_mode_results_project_id_keyword_id_analysis_date_key UNIQUE (project_id, keyword_id, analysis_date);


--
-- Name: ai_mode_snapshots ai_mode_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_snapshots
    ADD CONSTRAINT ai_mode_snapshots_pkey PRIMARY KEY (id);


--
-- Name: ai_mode_snapshots ai_mode_snapshots_project_id_snapshot_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_snapshots
    ADD CONSTRAINT ai_mode_snapshots_project_id_snapshot_date_key UNIQUE (project_id, snapshot_date);


--
-- Name: ai_overview_analysis ai_overview_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_overview_analysis
    ADD CONSTRAINT ai_overview_analysis_pkey PRIMARY KEY (id);


--
-- Name: gsc_properties gsc_properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gsc_properties
    ADD CONSTRAINT gsc_properties_pkey PRIMARY KEY (id);


--
-- Name: gsc_properties gsc_properties_user_id_site_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gsc_properties
    ADD CONSTRAINT gsc_properties_user_id_site_url_key UNIQUE (user_id, site_url);


--
-- Name: llm_model_changelog llm_model_changelog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model_changelog
    ADD CONSTRAINT llm_model_changelog_pkey PRIMARY KEY (id);


--
-- Name: llm_model_registry llm_model_registry_llm_provider_model_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model_registry
    ADD CONSTRAINT llm_model_registry_llm_provider_model_id_key UNIQUE (llm_provider, model_id);


--
-- Name: llm_model_registry llm_model_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model_registry
    ADD CONSTRAINT llm_model_registry_pkey PRIMARY KEY (id);


--
-- Name: llm_models llm_models_llm_provider_model_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_llm_provider_model_id_key UNIQUE (llm_provider, model_id);


--
-- Name: llm_models llm_models_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_analysis_lock llm_monitoring_analysis_lock_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_analysis_lock
    ADD CONSTRAINT llm_monitoring_analysis_lock_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_analysis_runs llm_monitoring_analysis_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_analysis_runs
    ADD CONSTRAINT llm_monitoring_analysis_runs_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_fanout_queries llm_monitoring_fanout_queries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_fanout_queries
    ADD CONSTRAINT llm_monitoring_fanout_queries_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_fanout_queries llm_monitoring_fanout_queries_result_id_position_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_fanout_queries
    ADD CONSTRAINT llm_monitoring_fanout_queries_result_id_position_key UNIQUE (result_id, "position");


--
-- Name: llm_monitoring_projects llm_monitoring_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_projects
    ADD CONSTRAINT llm_monitoring_projects_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_projects llm_monitoring_projects_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_projects
    ADD CONSTRAINT llm_monitoring_projects_user_id_name_key UNIQUE (user_id, name);


--
-- Name: llm_monitoring_queries llm_monitoring_queries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_queries
    ADD CONSTRAINT llm_monitoring_queries_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_queries llm_monitoring_queries_project_id_query_text_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_queries
    ADD CONSTRAINT llm_monitoring_queries_project_id_query_text_key UNIQUE (project_id, query_text);


--
-- Name: llm_monitoring_results llm_monitoring_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_results
    ADD CONSTRAINT llm_monitoring_results_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_results llm_monitoring_results_project_id_query_id_llm_provider_ana_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_results
    ADD CONSTRAINT llm_monitoring_results_project_id_query_id_llm_provider_ana_key UNIQUE (project_id, query_id, llm_provider, analysis_date);


--
-- Name: llm_monitoring_results llm_monitoring_results_units_consumed_check; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.llm_monitoring_results
    ADD CONSTRAINT llm_monitoring_results_units_consumed_check CHECK ((units_consumed >= 1)) NOT VALID;


--
-- Name: llm_monitoring_snapshots llm_monitoring_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_snapshots
    ADD CONSTRAINT llm_monitoring_snapshots_pkey PRIMARY KEY (id);


--
-- Name: llm_monitoring_snapshots llm_monitoring_snapshots_project_id_llm_provider_snapshot_d_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_snapshots
    ADD CONSTRAINT llm_monitoring_snapshots_project_id_llm_provider_snapshot_d_key UNIQUE (project_id, llm_provider, snapshot_date);


--
-- Name: llm_url_content_analysis llm_url_content_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_url_content_analysis
    ADD CONSTRAINT llm_url_content_analysis_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_events manual_ai_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_events
    ADD CONSTRAINT manual_ai_events_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_global_domains manual_ai_global_domains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_global_domains
    ADD CONSTRAINT manual_ai_global_domains_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_global_domains manual_ai_global_domains_project_id_keyword_id_analysis_dat_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_global_domains
    ADD CONSTRAINT manual_ai_global_domains_project_id_keyword_id_analysis_dat_key UNIQUE (project_id, keyword_id, analysis_date, detected_domain);


--
-- Name: manual_ai_keywords manual_ai_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_keywords
    ADD CONSTRAINT manual_ai_keywords_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_keywords manual_ai_keywords_project_id_keyword_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_keywords
    ADD CONSTRAINT manual_ai_keywords_project_id_keyword_key UNIQUE (project_id, keyword);


--
-- Name: manual_ai_projects manual_ai_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_projects
    ADD CONSTRAINT manual_ai_projects_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_projects manual_ai_projects_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_projects
    ADD CONSTRAINT manual_ai_projects_user_id_name_key UNIQUE (user_id, name);


--
-- Name: manual_ai_results manual_ai_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_results
    ADD CONSTRAINT manual_ai_results_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_results manual_ai_results_project_id_keyword_id_analysis_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_results
    ADD CONSTRAINT manual_ai_results_project_id_keyword_id_analysis_date_key UNIQUE (project_id, keyword_id, analysis_date);


--
-- Name: manual_ai_snapshots manual_ai_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_snapshots
    ADD CONSTRAINT manual_ai_snapshots_pkey PRIMARY KEY (id);


--
-- Name: manual_ai_snapshots manual_ai_snapshots_project_id_snapshot_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_snapshots
    ADD CONSTRAINT manual_ai_snapshots_project_id_snapshot_date_key UNIQUE (project_id, snapshot_date);


--
-- Name: oauth_connections oauth_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connections
    ADD CONSTRAINT oauth_connections_pkey PRIMARY KEY (id);


--
-- Name: oauth_connections oauth_connections_user_id_provider_google_account_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connections
    ADD CONSTRAINT oauth_connections_user_id_provider_google_account_id_key UNIQUE (user_id, provider, google_account_id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_token_key UNIQUE (token);


--
-- Name: project_collaborators project_collaborators_module_name_project_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators
    ADD CONSTRAINT project_collaborators_module_name_project_id_user_id_key UNIQUE (module_name, project_id, user_id);


--
-- Name: project_collaborators project_collaborators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators
    ADD CONSTRAINT project_collaborators_pkey PRIMARY KEY (id);


--
-- Name: project_invitations project_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations
    ADD CONSTRAINT project_invitations_pkey PRIMARY KEY (id);


--
-- Name: project_invitations project_invitations_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations
    ADD CONSTRAINT project_invitations_token_hash_key UNIQUE (token_hash);


--
-- Name: quota_usage_events quota_usage_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_usage_events
    ADD CONSTRAINT quota_usage_events_pkey PRIMARY KEY (id);


--
-- Name: seo_ai_analyses seo_ai_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seo_ai_analyses
    ADD CONSTRAINT seo_ai_analyses_pkey PRIMARY KEY (id);


--
-- Name: stripe_webhook_events stripe_webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_webhook_events
    ADD CONSTRAINT stripe_webhook_events_pkey PRIMARY KEY (event_id);


--
-- Name: llm_url_content_analysis uq_url_content_analysis_project_url; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_url_content_analysis
    ADD CONSTRAINT uq_url_content_analysis_project_url UNIQUE (project_id, url_hash);


--
-- Name: user_llm_api_keys user_llm_api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_llm_api_keys
    ADD CONSTRAINT user_llm_api_keys_pkey PRIMARY KEY (id);


--
-- Name: user_llm_api_keys user_llm_api_keys_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_llm_api_keys
    ADD CONSTRAINT user_llm_api_keys_user_id_key UNIQUE (user_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_google_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_id_key UNIQUE (google_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_admin_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_audit_created ON public.admin_audit_log USING btree (created_at DESC);


--
-- Name: idx_admin_audit_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_audit_target ON public.admin_audit_log USING btree (target_user_id);


--
-- Name: idx_agent_reports_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_reports_user ON public.agent_scanner_reports USING btree (user_email, created_at DESC);


--
-- Name: idx_ai_analysis_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_country ON public.ai_overview_analysis USING btree (country_code);


--
-- Name: idx_ai_analysis_has_ai; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_has_ai ON public.ai_overview_analysis USING btree (has_ai_overview);


--
-- Name: idx_ai_analysis_keyword; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_keyword ON public.ai_overview_analysis USING btree (keyword);


--
-- Name: idx_ai_analysis_site_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_site_date ON public.ai_overview_analysis USING btree (site_url, analysis_date);


--
-- Name: idx_ai_analysis_upsert; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_ai_analysis_upsert ON public.ai_overview_analysis USING btree (site_url, keyword, COALESCE(country_code, ''::character varying), ((analysis_date)::date), COALESCE(user_id, 0));


--
-- Name: idx_ai_analysis_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_user ON public.ai_overview_analysis USING btree (user_id);


--
-- Name: idx_ai_analysis_word_count; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analysis_word_count ON public.ai_overview_analysis USING btree (keyword_word_count);


--
-- Name: idx_ai_mode_events_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_events_project_date ON public.ai_mode_events USING btree (project_id, event_date);


--
-- Name: idx_ai_mode_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_events_type ON public.ai_mode_events USING btree (event_type);


--
-- Name: idx_ai_mode_keywords_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_keywords_active ON public.ai_mode_keywords USING btree (is_active);


--
-- Name: idx_ai_mode_keywords_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_keywords_project ON public.ai_mode_keywords USING btree (project_id);


--
-- Name: idx_ai_mode_projects_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_projects_active ON public.ai_mode_projects USING btree (is_active);


--
-- Name: idx_ai_mode_projects_topic_clusters; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_projects_topic_clusters ON public.ai_mode_projects USING gin (topic_clusters);


--
-- Name: idx_ai_mode_projects_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_projects_user ON public.ai_mode_projects USING btree (user_id);


--
-- Name: idx_ai_mode_results_brand_mentioned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_results_brand_mentioned ON public.ai_mode_results USING btree (brand_mentioned);


--
-- Name: idx_ai_mode_results_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_results_date ON public.ai_mode_results USING btree (analysis_date);


--
-- Name: idx_ai_mode_results_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_results_project_date ON public.ai_mode_results USING btree (project_id, analysis_date);


--
-- Name: idx_ai_mode_snapshots_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_snapshots_project_date ON public.ai_mode_snapshots USING btree (project_id, snapshot_date);


--
-- Name: idx_ai_mode_user_paused; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_mode_user_paused ON public.ai_mode_projects USING btree (user_id, is_paused_by_quota);


--
-- Name: idx_analysis_runs_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analysis_runs_started ON public.llm_monitoring_analysis_runs USING btree (started_at DESC);


--
-- Name: idx_analysis_runs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analysis_runs_status ON public.llm_monitoring_analysis_runs USING btree (status);


--
-- Name: idx_changelog_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_changelog_date ON public.llm_model_changelog USING btree (created_at);


--
-- Name: idx_changelog_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_changelog_provider ON public.llm_model_changelog USING btree (llm_provider);


--
-- Name: idx_fanout_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fanout_project_date ON public.llm_monitoring_fanout_queries USING btree (project_id, analysis_date);


--
-- Name: idx_fanout_project_host; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fanout_project_host ON public.llm_monitoring_fanout_queries USING btree (project_id, url_host) WHERE (url_host IS NOT NULL);


--
-- Name: idx_fanout_project_query; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fanout_project_query ON public.llm_monitoring_fanout_queries USING btree (project_id, query_normalized) WHERE ((action)::text = 'search'::text);


--
-- Name: idx_global_domains_competitor_flag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_global_domains_competitor_flag ON public.manual_ai_global_domains USING btree (project_id, is_selected_competitor, analysis_date);


--
-- Name: idx_global_domains_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_global_domains_domain ON public.manual_ai_global_domains USING btree (detected_domain);


--
-- Name: idx_global_domains_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_global_domains_project_date ON public.manual_ai_global_domains USING btree (project_id, analysis_date);


--
-- Name: idx_gsc_props_conn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gsc_props_conn ON public.gsc_properties USING btree (connection_id);


--
-- Name: idx_gsc_props_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gsc_props_user ON public.gsc_properties USING btree (user_id);


--
-- Name: idx_llm_models_current; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_models_current ON public.llm_model_registry USING btree (is_current);


--
-- Name: idx_llm_models_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_models_provider ON public.llm_model_registry USING btree (llm_provider);


--
-- Name: idx_llm_monitoring_prompt_clusters; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_monitoring_prompt_clusters ON public.llm_monitoring_projects USING gin (prompt_clusters);


--
-- Name: idx_llm_proj_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_proj_active ON public.llm_monitoring_projects USING btree (is_active);


--
-- Name: idx_llm_proj_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_proj_user ON public.llm_monitoring_projects USING btree (user_id);


--
-- Name: idx_llm_proj_user_paused; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_proj_user_paused ON public.llm_monitoring_projects USING btree (user_id, is_paused_by_quota);


--
-- Name: idx_llm_queries_proj; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_queries_proj ON public.llm_monitoring_queries USING btree (project_id);


--
-- Name: idx_llm_queries_prompt_set; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_queries_prompt_set ON public.llm_monitoring_queries USING btree (project_id, prompt_set) WHERE (prompt_set IS NOT NULL);


--
-- Name: idx_llm_queries_topic_cluster; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_queries_topic_cluster ON public.llm_monitoring_queries USING btree (project_id, topic_cluster) WHERE (topic_cluster IS NOT NULL);


--
-- Name: idx_llm_results_date_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_date_project ON public.llm_monitoring_results USING btree (analysis_date, project_id);


--
-- Name: idx_llm_results_has_error; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_has_error ON public.llm_monitoring_results USING btree (has_error) WHERE (has_error = true);


--
-- Name: idx_llm_results_mentioned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_mentioned ON public.llm_monitoring_results USING btree (brand_mentioned);


--
-- Name: idx_llm_results_position_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_position_source ON public.llm_monitoring_results USING btree (position_source) WHERE (position_source IS NOT NULL);


--
-- Name: idx_llm_results_proj_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_proj_date ON public.llm_monitoring_results USING btree (project_id, analysis_date);


--
-- Name: idx_llm_results_prompt_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_prompt_version ON public.llm_monitoring_results USING btree (prompt_version) WHERE (prompt_version IS NOT NULL);


--
-- Name: idx_llm_results_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_results_provider ON public.llm_monitoring_results USING btree (llm_provider);


--
-- Name: idx_llm_snapshots_proj_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_snapshots_proj_date ON public.llm_monitoring_snapshots USING btree (project_id, snapshot_date);


--
-- Name: idx_llm_snapshots_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_snapshots_provider ON public.llm_monitoring_snapshots USING btree (llm_provider);


--
-- Name: idx_manual_ai_projects_competitors; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_ai_projects_competitors ON public.manual_ai_projects USING gin (selected_competitors);


--
-- Name: idx_manual_ai_projects_topic_clusters; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_ai_projects_topic_clusters ON public.manual_ai_projects USING gin (topic_clusters);


--
-- Name: idx_manual_ai_projects_user_paused; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_ai_projects_user_paused ON public.manual_ai_projects USING btree (user_id, is_paused_by_quota);


--
-- Name: idx_manual_events_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_events_project_date ON public.manual_ai_events USING btree (project_id, event_date);


--
-- Name: idx_manual_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_events_type ON public.manual_ai_events USING btree (event_type);


--
-- Name: idx_manual_keywords_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_keywords_active ON public.manual_ai_keywords USING btree (is_active);


--
-- Name: idx_manual_keywords_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_keywords_project ON public.manual_ai_keywords USING btree (project_id);


--
-- Name: idx_manual_projects_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_projects_active ON public.manual_ai_projects USING btree (is_active);


--
-- Name: idx_manual_projects_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_projects_user ON public.manual_ai_projects USING btree (user_id);


--
-- Name: idx_manual_results_ai_overview; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_results_ai_overview ON public.manual_ai_results USING btree (has_ai_overview);


--
-- Name: idx_manual_results_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_results_date ON public.manual_ai_results USING btree (analysis_date);


--
-- Name: idx_manual_results_domain_mentioned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_results_domain_mentioned ON public.manual_ai_results USING btree (domain_mentioned);


--
-- Name: idx_manual_results_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_results_project_date ON public.manual_ai_results USING btree (project_id, analysis_date);


--
-- Name: idx_manual_snapshots_project_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manual_snapshots_project_date ON public.manual_ai_snapshots USING btree (project_id, snapshot_date);


--
-- Name: idx_model_approval_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_approval_token ON public.llm_model_registry USING btree (approval_token) WHERE (approval_token IS NOT NULL);


--
-- Name: idx_oauth_connections_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_connections_provider ON public.oauth_connections USING btree (provider);


--
-- Name: idx_oauth_connections_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_connections_user ON public.oauth_connections USING btree (user_id);


--
-- Name: idx_password_reset_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_expires ON public.password_reset_tokens USING btree (expires_at);


--
-- Name: idx_password_reset_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_token ON public.password_reset_tokens USING btree (token);


--
-- Name: idx_password_reset_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: idx_project_collaborators_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_collaborators_owner ON public.project_collaborators USING btree (owner_user_id);


--
-- Name: idx_project_collaborators_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_collaborators_project ON public.project_collaborators USING btree (module_name, project_id);


--
-- Name: idx_project_collaborators_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_collaborators_user ON public.project_collaborators USING btree (user_id);


--
-- Name: idx_project_invitations_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_invitations_email ON public.project_invitations USING btree (lower(invitee_email));


--
-- Name: idx_project_invitations_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_invitations_owner ON public.project_invitations USING btree (owner_user_id, status);


--
-- Name: idx_project_invitations_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_invitations_project ON public.project_invitations USING btree (module_name, project_id, status);


--
-- Name: idx_project_invitations_unique_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_project_invitations_unique_pending ON public.project_invitations USING btree (module_name, project_id, lower(invitee_email)) WHERE ((status)::text = 'pending'::text);


--
-- Name: idx_quota_events_optype_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quota_events_optype_timestamp ON public.quota_usage_events USING btree (operation_type, "timestamp");


--
-- Name: idx_quota_events_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quota_events_project ON public.quota_usage_events USING btree (user_id, source, ((metadata ->> 'project_id'::text)), "timestamp");


--
-- Name: idx_quota_events_source_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quota_events_source_timestamp ON public.quota_usage_events USING btree (source, "timestamp");


--
-- Name: idx_quota_events_timestamp_billing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quota_events_timestamp_billing ON public.quota_usage_events USING btree ("timestamp");


--
-- Name: idx_quota_events_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quota_events_user_date ON public.quota_usage_events USING btree (user_id, "timestamp");


--
-- Name: idx_seo_ai_analyses_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_seo_ai_analyses_created ON public.seo_ai_analyses USING btree (created_at DESC);


--
-- Name: idx_seo_ai_analyses_user_site; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_seo_ai_analyses_user_site ON public.seo_ai_analyses USING btree (user_id, site_url);


--
-- Name: idx_stripe_webhook_events_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stripe_webhook_events_received ON public.stripe_webhook_events USING btree (received_at DESC);


--
-- Name: idx_url_content_analysis_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_url_content_analysis_project ON public.llm_url_content_analysis USING btree (project_id);


--
-- Name: idx_users_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_active ON public.users USING btree (is_active);


--
-- Name: idx_users_billing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_billing_status ON public.users USING btree (billing_status);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_google_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_google_id ON public.users USING btree (google_id);


--
-- Name: idx_users_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_plan ON public.users USING btree (plan);


--
-- Name: admin_audit_log admin_audit_log_admin_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_admin_user_id_fkey FOREIGN KEY (admin_user_id) REFERENCES public.users(id);


--
-- Name: ai_brand_links ai_brand_links_ai_mode_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_ai_mode_project_id_fkey FOREIGN KEY (ai_mode_project_id) REFERENCES public.ai_mode_projects(id) ON DELETE SET NULL;


--
-- Name: ai_brand_links ai_brand_links_llm_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_llm_project_id_fkey FOREIGN KEY (llm_project_id) REFERENCES public.llm_monitoring_projects(id) ON DELETE SET NULL;


--
-- Name: ai_brand_links ai_brand_links_manual_ai_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_manual_ai_project_id_fkey FOREIGN KEY (manual_ai_project_id) REFERENCES public.manual_ai_projects(id) ON DELETE SET NULL;


--
-- Name: ai_brand_links ai_brand_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_links
    ADD CONSTRAINT ai_brand_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: ai_brand_score_snapshots ai_brand_score_snapshots_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_brand_score_snapshots
    ADD CONSTRAINT ai_brand_score_snapshots_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.ai_brand_links(id) ON DELETE CASCADE;


--
-- Name: ai_mode_events ai_mode_events_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_events
    ADD CONSTRAINT ai_mode_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_mode_projects(id) ON DELETE CASCADE;


--
-- Name: ai_mode_events ai_mode_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_events
    ADD CONSTRAINT ai_mode_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_mode_keywords ai_mode_keywords_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_keywords
    ADD CONSTRAINT ai_mode_keywords_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_mode_projects(id) ON DELETE CASCADE;


--
-- Name: ai_mode_projects ai_mode_projects_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_projects
    ADD CONSTRAINT ai_mode_projects_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: ai_mode_results ai_mode_results_keyword_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_results
    ADD CONSTRAINT ai_mode_results_keyword_id_fkey FOREIGN KEY (keyword_id) REFERENCES public.ai_mode_keywords(id) ON DELETE CASCADE;


--
-- Name: ai_mode_results ai_mode_results_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_results
    ADD CONSTRAINT ai_mode_results_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_mode_projects(id) ON DELETE CASCADE;


--
-- Name: ai_mode_snapshots ai_mode_snapshots_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_mode_snapshots
    ADD CONSTRAINT ai_mode_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_mode_projects(id) ON DELETE CASCADE;


--
-- Name: ai_overview_analysis ai_overview_analysis_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_overview_analysis
    ADD CONSTRAINT ai_overview_analysis_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: gsc_properties gsc_properties_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gsc_properties
    ADD CONSTRAINT gsc_properties_connection_id_fkey FOREIGN KEY (connection_id) REFERENCES public.oauth_connections(id) ON DELETE CASCADE;


--
-- Name: gsc_properties gsc_properties_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gsc_properties
    ADD CONSTRAINT gsc_properties_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_fanout_queries llm_monitoring_fanout_queries_result_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_fanout_queries
    ADD CONSTRAINT llm_monitoring_fanout_queries_result_id_fkey FOREIGN KEY (result_id) REFERENCES public.llm_monitoring_results(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_projects llm_monitoring_projects_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_projects
    ADD CONSTRAINT llm_monitoring_projects_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_queries llm_monitoring_queries_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_queries
    ADD CONSTRAINT llm_monitoring_queries_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.llm_monitoring_projects(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_results llm_monitoring_results_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_results
    ADD CONSTRAINT llm_monitoring_results_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.llm_monitoring_projects(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_results llm_monitoring_results_query_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_results
    ADD CONSTRAINT llm_monitoring_results_query_id_fkey FOREIGN KEY (query_id) REFERENCES public.llm_monitoring_queries(id) ON DELETE CASCADE;


--
-- Name: llm_monitoring_snapshots llm_monitoring_snapshots_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_monitoring_snapshots
    ADD CONSTRAINT llm_monitoring_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.llm_monitoring_projects(id) ON DELETE CASCADE;


--
-- Name: llm_url_content_analysis llm_url_content_analysis_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_url_content_analysis
    ADD CONSTRAINT llm_url_content_analysis_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.llm_monitoring_projects(id) ON DELETE CASCADE;


--
-- Name: manual_ai_events manual_ai_events_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_events
    ADD CONSTRAINT manual_ai_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.manual_ai_projects(id) ON DELETE CASCADE;


--
-- Name: manual_ai_events manual_ai_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_events
    ADD CONSTRAINT manual_ai_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: manual_ai_global_domains manual_ai_global_domains_keyword_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_global_domains
    ADD CONSTRAINT manual_ai_global_domains_keyword_id_fkey FOREIGN KEY (keyword_id) REFERENCES public.manual_ai_keywords(id) ON DELETE CASCADE;


--
-- Name: manual_ai_global_domains manual_ai_global_domains_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_global_domains
    ADD CONSTRAINT manual_ai_global_domains_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.manual_ai_projects(id) ON DELETE CASCADE;


--
-- Name: manual_ai_keywords manual_ai_keywords_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_keywords
    ADD CONSTRAINT manual_ai_keywords_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.manual_ai_projects(id) ON DELETE CASCADE;


--
-- Name: manual_ai_projects manual_ai_projects_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_projects
    ADD CONSTRAINT manual_ai_projects_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: manual_ai_results manual_ai_results_keyword_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_results
    ADD CONSTRAINT manual_ai_results_keyword_id_fkey FOREIGN KEY (keyword_id) REFERENCES public.manual_ai_keywords(id) ON DELETE CASCADE;


--
-- Name: manual_ai_results manual_ai_results_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_results
    ADD CONSTRAINT manual_ai_results_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.manual_ai_projects(id) ON DELETE CASCADE;


--
-- Name: manual_ai_snapshots manual_ai_snapshots_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_ai_snapshots
    ADD CONSTRAINT manual_ai_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.manual_ai_projects(id) ON DELETE CASCADE;


--
-- Name: oauth_connections oauth_connections_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connections
    ADD CONSTRAINT oauth_connections_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_collaborators project_collaborators_invited_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators
    ADD CONSTRAINT project_collaborators_invited_by_user_id_fkey FOREIGN KEY (invited_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: project_collaborators project_collaborators_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators
    ADD CONSTRAINT project_collaborators_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_collaborators project_collaborators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_collaborators
    ADD CONSTRAINT project_collaborators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_invitations project_invitations_accepted_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations
    ADD CONSTRAINT project_invitations_accepted_by_user_id_fkey FOREIGN KEY (accepted_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: project_invitations project_invitations_inviter_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations
    ADD CONSTRAINT project_invitations_inviter_user_id_fkey FOREIGN KEY (inviter_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_invitations project_invitations_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_invitations
    ADD CONSTRAINT project_invitations_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quota_usage_events quota_usage_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_usage_events
    ADD CONSTRAINT quota_usage_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: seo_ai_analyses seo_ai_analyses_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seo_ai_analyses
    ADD CONSTRAINT seo_ai_analyses_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_llm_api_keys user_llm_api_keys_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_llm_api_keys
    ADD CONSTRAINT user_llm_api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict LVe2enD77mkgaAEuQY1eDHPFNJJRUPRnrbbLtmavCSrCwFdzBGybqPibbsNcFeF

